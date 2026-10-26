# Design notes: Emergency triage queue

A terminal program that replaces the emergency unit's whiteboard with a priority queue. Patients are attended by triage level (1 critical, 2 urgent, 3 standard). Within a level, they are attended in arrival order. Only Python's standard library is used.

## Layout

| File | Contents |
|---|---|
| `triage/models.py` | `TriageLevel` enum and the `Patient` dataclass (`name`, `triage_level`, `arrived_at`) |
| `triage/queue.py` | `TriageQueue` (`enqueue`, `dequeue`, `peek`, `list_queue`, `stats`) and `EmptyQueueError` |
| `triage/cli.py` | Text menu. Input and output can be swapped so tests can script a session |
| `main.py` | Entry point |
| `tests/` | `unittest` suite. `test_edge_cases.py` has one test group per correctness requirement |

Run the app with `python3 main.py` and the tests with `python3 -m unittest -v`. Python 3.9 or newer is required.

## 1. Why a heap

`TriageQueue` keeps a single `heapq` min-heap. Each entry is a tuple:

```python
(triage_level, seq, patient)
```

Tuples compare element by element. The heap therefore orders by triage level first, then by `seq`, a counter that goes up by one on every `enqueue`.

**A critical arrival doesn't re-sort the queue.** `heappush` places the new entry at the bottom and swaps it upward until its parent is smaller. That takes at most log₂(n) steps: about 10 for 1,000 waiting patients. The rest of the queue isn't touched.

### Alternatives considered

| Structure | Enqueue | Dequeue | List in order | Stats | Verdict |
|---|---|---|---|---|---|
| Single `deque` | O(n): find the spot, then `insert` | O(1) | O(n) | O(n) | `deque` is built for appending at the ends. Putting a critical patient in the middle means scanning and shifting the whole line. |
| Sorted list (`bisect.insort`) | O(n): the search is O(log n), but every later element shifts | O(1) if kept reversed | O(n) | O(n) | Correct but linear per arrival. Re-sorting on every insert is worse. |
| Three `deque`s, one per level | O(1) | O(1) | O(n) | O(1) | A strong option. See below. |
| **`heapq` min-heap** (chosen) | **O(log n)** | **O(log n)** | O(n log n), on a copy | O(n) | One structure, ordered by one comparable key. |

**Three deques versus a heap.** For exactly three fixed levels, one deque per level is just as correct and slightly faster. The heap was chosen because the ordering rule lives in a single sort key, not in the shape of the data:
- If the rule changes, only the key tuple changes. Examples are a sub-priority within a level or a 5-level triage scale such as ESI or Manchester. With a 5-level scale, the queue class needs no edits, only the `TriageLevel` enum and the menu text.
- With buckets, each new rule means more buckets and more code to walk them in order.

At emergency-room volumes (tens to hundreds of patients), O(log n) versus O(1) makes no practical difference. Callers only see the public methods, so the internals could switch to buckets later without changing any caller.

The read-only operations are deliberately simple. `list_queue()` sorts a copy of the heap and never changes the real one. `stats()` counts by scanning the heap rather than keeping separate counters. Separate counters would be a second record that could drift out of sync with the heap.

## 2. Why `seq` breaks ties and `arrived_at` doesn't

`arrived_at` is recorded for display and audit only. It is never used for ordering. Ties are broken by `seq`, for three reasons:

1. **Timestamps can be equal.** Two registrations within the clock's resolution get the same `arrived_at`. The tuple comparison would then move on to the `Patient` objects. `Patient` defines no ordering, so Python would raise `TypeError` in the middle of a `heappush`.
2. **The wall clock can go backwards.** `datetime.now()` is local time, which jumps back an hour when daylight saving time ends and can also be corrected by NTP. A patient registered after such a jump would be ordered ahead of people who arrived earlier.
3. **`seq` is unique and only ever increases.** It is assigned under the same lock as the push. Arrival order is therefore exactly the order in which the queue accepted the patients, and the comparison never reaches `Patient`.

`test_identical_arrival_times_still_keep_arrival_order` covers the equal-timestamp case.

`Patient` is a frozen dataclass for a related reason. If code changed a patient's `triage_level` while they were in the heap, the heap's order would silently become wrong. Making the field read-only turns that mistake into an immediate error.

## 3. Concurrency: a nurse calls the next patient while a critical patient is registered

### What can go wrong without protection

The queue's shared state is the heap list and the `seq` counter. Without a lock, `dequeue` has a gap between "is the queue empty?" and "remove the first entry". Another worker can take the last patient in that gap. The second worker then crashes with a bare `IndexError` instead of getting a clean "queue is empty" error. `enqueue` has the same kind of gap between taking a `seq` number and pushing the entry. The lock closes these gaps without relying on interpreter details such as CPython's global interpreter lock.

### What the code does

Every public method of `TriageQueue` holds one `threading.Lock` for its whole duration. Each operation therefore happens completely before or completely after any other. Suppose Nurse A calls the next patient at the same moment Nurse B registers critical patient Carla, while Beto (level 2) is at the front. There are only two possible outcomes:

| Who gets the lock first | Nurse A attends | Front of the queue afterwards |
|---|---|---|
| B (the enqueue) | Carla | Beto |
| A (the dequeue) | Beto | Carla |

Both outcomes are correct. In the second, Beto was already being called when Carla arrived, and Carla is next with nobody able to cut ahead of her. The following can never happen:
- a lost patient
- a patient given to two nurses
- a heap left in a broken order

### The order of state changes that prevents double-processing: claim by removal

`dequeue()` does these steps in this order:

1. Acquire the lock.
2. If the heap is empty, raise `EmptyQueueError`. Nothing has changed, and the `with` block releases the lock.
3. `heappop`. The patient is now removed from the shared state.
4. Release the lock.
5. Return the patient to the caller, who attends them.

The patient leaves the queue (step 3) **before** anyone can act on them (step 5), and no other worker can look at the heap between steps 1 and 4. Once a nurse has the patient, nobody else can get them.

The pattern to avoid is "peek, attend, then dequeue":

```python
patient = queue.peek()   # A and B both peek and both see Beto
attend(patient)          # Beto is attended twice
queue.dequeue()          # the second dequeue removes the next person in line, who is never seen
```

That is why the menu's "call next" calls `dequeue()` directly (`triage/cli.py`, `_call_next`). `peek()` is only meant for display.

### Evidence

`ConcurrencyTests` in `tests/test_edge_cases.py` runs 4 threads adding 1,000 patients while 4 threads call them. It checks that every patient is attended exactly once and that the queue ends empty. It also repeats the "one call against one critical arrival" race 200 times and accepts only the two outcomes in the table above.

To make sure the 8-thread test really depends on the lock, a copy of the code with the lock replaced by a no-op was run against it. The test failed 5 out of 5 times with the bare `IndexError` described above. The single-race test passed without the lock. With only one push racing one pop, every possible interleaving still ends in one of the two valid outcomes. The failure needs two workers competing for the last patient. The 8-thread test is the one that guards the lock.

### When this runs inside a larger application

A `threading.Lock` only protects workers inside one process. Once several servers share the queue through a database, the same "claim by removal" rule becomes a single atomic database statement:

- **A conditional update.** For example `UPDATE patients SET status = 'in_progress', nurse_id = ? WHERE id = ? AND status = 'waiting'`. The nurse has claimed the patient only if exactly one row was updated.
- **Or a locking select** (PostgreSQL): `SELECT … WHERE status = 'waiting' ORDER BY triage_level, arrival_seq LIMIT 1 FOR UPDATE SKIP LOCKED`. Concurrent workers skip rows another worker has already locked.

In both cases, ordering still comes from a database sequence column (`arrival_seq`), not from a timestamp.

## Known limitations

- **Data lives only in memory**, so closing the program loses the queue.
- **There is no re-triage or removal by name.** A patient's level can only change by dequeuing them and enqueuing them again, which sends them to the back of their new level.
- **Patients have no ID.** The same `Patient` can be enqueued twice. Integration should add a patient ID and reject duplicates.
- **A claimed patient can't be returned to the queue in their old place.** If the nurse who claimed a patient can't attend them, enqueuing them again puts them at the back of their level. A database version would hold the patient in an `in_progress` state with a timeout instead.
