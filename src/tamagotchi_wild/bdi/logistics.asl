!boot.

+!boot <-
    .mark_bdi_ready.

+bowl_empty(TaskId, CageId, BowlId) <-
    !ensure_food(TaskId, CageId, BowlId).

+!ensure_food(TaskId, CageId, BowlId) <-
    .request_feeding(TaskId, CageId, BowlId).

+feeding_completed(TaskId) <-
    .finish_feeding_workflow(TaskId, completed).

+feeding_failed(TaskId) <-
    .finish_feeding_workflow(TaskId, failed).

+transport_requested(TaskId, AnimalId, CageId, outbound) <-
    .execute_transport(TaskId, AnimalId, CageId, outbound).

+transport_requested(TaskId, AnimalId, CageId, return) <-
    .execute_transport(TaskId, AnimalId, CageId, return).
