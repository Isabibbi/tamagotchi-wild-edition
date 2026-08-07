!boot.

+!boot <-
    .mark_bdi_ready.

+sick_animal(TaskId, AnimalId, CageId) <-
    !ensure_treatment(TaskId, AnimalId, CageId).

+!ensure_treatment(TaskId, AnimalId, CageId) <-
    .request_medical_transport(TaskId, AnimalId, CageId, outbound).

+patient_ready(TaskId, AnimalId, CageId) <-
    !treat_patient(TaskId, AnimalId, CageId).

+!treat_patient(TaskId, AnimalId, CageId) <-
    .execute_medical_treatment(TaskId, AnimalId, CageId).

+treatment_succeeded(TaskId, AnimalId, CageId) <-
    !ensure_return(TaskId, AnimalId, CageId).

+!ensure_return(TaskId, AnimalId, CageId) <-
    .request_medical_transport(TaskId, AnimalId, CageId, return).

+animal_returned(TaskId, AnimalId, CageId) <-
    .finish_medical_scenario(TaskId, completed).

+medical_failed(TaskId) <-
    .finish_medical_scenario(TaskId, failed).
