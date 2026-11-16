# Stopping a launch — 0.9.0 development

A `run-*` or `replay-*` launch holds its task's lease for the whole
`timeout_seconds + commit_margin_seconds`, up to about six hours. Before
0.9.0 a launch stopped by an operator or a supervisor left that lease held
until it expired, so every relaunch was refused as `task is leased to another
attempt`. Stopping the launcher also skipped the clean-up that kills the
program's process group, so the program could run on, unsupervised and past
its timeout, beside a later attempt of the same task. This page describes
what happens now. It applies to all three frozen routes (study, census,
program); receipts, schemas and verifiers are unchanged.

## A stop signal: SIGTERM, SIGINT, SIGHUP

While the lease is held and the outcome is not yet decided, any of these
signals sent to the launcher ends the attempt:

1. The child is killed: for a program, its **whole process group**, as after
   a timeout; for a verifier child, the child. The launcher waits for it.
2. In one transaction the task returns to `pending` and an `interrupted`
   event with the fence and the signal name is appended.
   **The attempt stays charged and the fence stays spent**: the stopped
   attempt can never complete, and the next grant gets the next fence.
3. Nothing is exported and no receipt is written. The command prints

   ```json
   {"budget":{"maximum":5,"spent":1},"execution":"interrupted","fence":1,
    "lease_released":true,"signal":"SIGTERM","task_id":"program-…","task_state":"pending"}
   ```

   and exits 2. A relaunch is accepted at once if the ceiling has room.

`lease_released` is false only if another attempt already holds the task
(the lease had expired and was reclaimed); the task is then left alone.

Outside that window a stop waits for the step in progress and is then
delivered as it would have been without the launcher's handlers (by default
the process ends):

- while the lease is being taken: if it is granted, the attempt is then
  interrupted as above; if not, the process ends without printing;
- after the outcome is decided: the receipt is committed and exported first,
  then the process ends without printing. Run the command again; it prints
  the receipt as `not_rerun`.

A stop is never taken halfway through a commit. A second stop during the
clean-up is absorbed. A signal that was ignored when the launch started, as
under `nohup`, stays ignored. The handlers exist only in the main thread of
the process; a library caller in another thread gets none, and an in-process
caller in the main thread gets the exception `Interrupted` (not an
`Exception`), whose `result` is the object above, after the task was
released. Send the stop to the launcher; a signal sent to the program alone
ends only the program, which is an `EXECUTION_FAILED` outcome as before.

## A launcher that dies hard (SIGKILL, power loss)

No handler runs. On Linux every route's child is started with the
parent-death signal set to SIGKILL (`prctl(PR_SET_PDEATHSIG)`), so the
kernel kills the program, or the verifier child, when the launcher dies.
This covers the child itself: **a process the program started does not
receive it** and survives unless it ends with the program. Elsewhere the
signal is not available and the child may run on.

The lease stays held. Wait for it to expire, or free it at once:

```sh
PYTHONPATH=src python -m hypersearch abandon-attempt --db /outside-source/tasks.sqlite \
  --task program-… --fence 1 --reason "launcher killed by the supervisor's time limit"
```

The task id is the one a refused start prints; the fence is in
`status --db … --budget N` (the database's ceiling). The command:

- refuses unless the task is `running` with exactly that fence (a completed
  task, a pending task and a stale fence are refused);
- refuses unless the lease recorded its holder and that holder is dead.
  Since 0.9.0 each lease a frozen route takes records the launcher: process
  id, start time, kernel boot id and host name. The holder is **alive** while
  a process with that id and start time runs on this host and boot; a
  reused process id has another start time and is not the holder; a zombie
  is dead; another boot id means the host was restarted, so it is dead.
  Another host name, or no `/proc`, is **unknown** and refused. A lease
  without a record (taken by an earlier release, the demo or the review
  workflow) is refused: it can only expire;
- then, in one transaction, returns the task to `pending` and appends an
  `abandoned` event with the fence, the reason and the holder. The attempt
  stays charged.

It prints `"execution": "abandoned"` with the task, fence, reason, holder,
budget and state, and exits 0. A refusal writes nothing, prints the reason on
standard error and exits 2. **It never deletes or changes results, events,
receipts or exports.** Run it on the host and in the process namespace of
the launcher; a container with its own process ids sees another host name or
other processes.

## Database compatibility

The store gains one table, `event_details` (event sequence, canonical JSON),
created when a database is opened. The earlier tables keep their exact
definitions, so a 0.9.0 database still opens in 0.8.0, and a released or
abandoned task (state `pending`) is granted by 0.8.0 as by 0.9.0. A database
written by an earlier release gains the empty table and is otherwise
unchanged; its events have no details. `status` now prints each event's `detail` (null when it has none).
New event kinds: `interrupted` and `abandoned`. A start refused before any
lease still charges nothing and writes no event, as before.

## Limits

- The window is the main thread of one process. A launcher started from a
  thread, or with the stop signals blocked, is not covered.
- The parent-death signal is Linux only and reaches the child, not its
  descendants. A program that leaves its process group survives any stop, as
  it survives a timeout.
- Liveness is read from `/proc` and is cooperative: the host's process table
  and clock are trusted, and the database must be on a local filesystem.
- Optional heartbeats (short leases renewed by the launcher) are not
  implemented; a lease still lasts the timeout plus the margin.

## Status — 2026-11-16

Motivation: an operator stopped a launch about half a minute in; the
relaunch was refused and the family waited for the lease to expire, and the
code path let the program outlive its launcher.

Implemented with tests written first and failing against 0.8.0, then the
fix: the real command line stopped by each of the three signals (program
group gone, `interrupted` recorded, lease released, attempt charged,
relaunch at once as fence 2); a SIGKILLed launcher whose program dies with
it, `abandon-attempt` refused while it lives and accepted after; store-level
refusals and evidence preservation; holder liveness with a reused process id
and an unreaped process; the signal guard; a stop during a commit; databases
of 0.8.0 in both directions. Each new check was removed in turn in a scratch
copy to confirm a test fails. Author checks only, Linux, Python 3.11 to 3.13;
independent review, public CI and consumer adoption are separate gates. No
research executed, no claim promoted.
