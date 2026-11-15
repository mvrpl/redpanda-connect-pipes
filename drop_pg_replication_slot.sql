SELECT pg_terminate_backend(3076592);
SELECT pg_drop_replication_slot('py_cdc_slot');