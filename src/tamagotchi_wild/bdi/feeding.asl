!boot.

+!boot <-
    .mark_bdi_ready.

+feeding_task(TaskId, CageId, BowlId) <-
    !complete_feeding(TaskId, CageId, BowlId).

+!complete_feeding(TaskId, CageId, BowlId) <-
    .execute_feeding(TaskId, CageId, BowlId).

+feeding_succeeded(TaskId) <-
    .record_feeding_outcome(TaskId, completed).

+feeding_failed(TaskId) <-
    .record_feeding_outcome(TaskId, failed).
