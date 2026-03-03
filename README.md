# Managed Slurm Integration Tests

This directory provides six playbooks for exercising lifecycle behavior on a single Ubuntu VM:

- setup/teardown of a simple baseline
- setup/teardown of intentionally messy state
- setup that fails halfway (by design) and rollback validation

All playbooks emit webhook checkpoints to a custom endpoint and include rollback logic for partial runs.

## Folder Layout

- `playbooks/01_simple_setup.yml`
- `playbooks/02_simple_teardown.yml`
- `playbooks/03_messy_setup.yml`
- `playbooks/04_messy_teardown.yml`
- `playbooks/05_intentional_failure_setup.yml`
- `playbooks/06_intentional_failure_teardown.yml`
- `tasks/webhook_event.yml` - shared webhook POST logic
- `tasks/rollback_simple.yml` - shared rollback tasks for simple setup
- `tasks/rollback_messy.yml` - shared rollback tasks for messy setup
- `tasks/rollback_fail_halfway.yml` - shared rollback tasks for fail-halfway setup
- `vars/webhook.yml` - default webhook configuration
- `inventories/single-ubuntu.ini` - sample inventory targeting one VM

## Webhook Contract

By default, each playbook sends `POST` requests to:

- `http://<webhook_host>:<webhook_port>/awx/logging`

Payload fields include:

- `status` (`running`, `success`, `failed`, `rolled_back`)
- `description`
- `error_code`
- `checkpoint`
- `suite`
- `run_id`
- `host`
- `playbook`
- `remediation` (`job_template_id`, `job_template_name`, `rollback_playbook`)
- `timestamp_utc`

This supports:

- progress visibility during run
- failure visibility with context
- optional downstream automation that can map failures to remediation jobs

## Configure Webhook

Edit `vars/webhook.yml` or override values at runtime:

- `webhook_host` - webhook service IP or DNS name
- `webhook_port`
- `webhook_endpoint` (defaults to `/awx/logging`)
- `webhook_token` (optional bearer token)
- `remediation_job_template_id` (optional)
- `remediation_job_template_name` (optional)

Example with runtime overrides:

```bash
ansible-playbook -i inventories/single-ubuntu.ini playbooks/01_simple_setup.yml \
  -e webhook_host=10.3.8.90 \
  -e webhook_port=5000 \
  -e webhook_token='replace-me' \
  -e remediation_job_template_id=42 \
  -e remediation_job_template_name='managed-slurm-remediate-simple'
```

## Run Order

Recommended lifecycle:

1. `01_simple_setup.yml`
2. `02_simple_teardown.yml`
3. `03_messy_setup.yml`
4. `04_messy_teardown.yml`
5. `05_intentional_failure_setup.yml` (expected to fail and roll back)
6. `06_intentional_failure_teardown.yml`

## Failure and Rollback Behavior

Each setup playbook uses `block/rescue/always`:

- **block**: apply changes and send running checkpoints
- **rescue**: on failure, send failure checkpoint and execute rollback tasks
- **always**: send final status checkpoint

Teardown playbooks are idempotent and can be run even if setup failed or was interrupted.

## Cancellation Notes

Ansible can execute `rescue/always` reliably for task failures. For operator-initiated cancellation, cleanup behavior depends on exactly how the run is stopped:

- Graceful interruption has a better chance to run teardown logic and webhook finalization.
- Hard termination may stop execution before rollback/final webhook tasks run.

For high-assurance cancellation handling in production:

- trigger teardown/remediation from the orchestrator (for example AWX workflow nodes on failure/cancel)
- keep `rollback_playbook` and remediation metadata in webhook payloads, as already included here

## Quick Validation Commands

Syntax checks:

```bash
ansible-playbook -i inventories/single-ubuntu.ini playbooks/01_simple_setup.yml --syntax-check
ansible-playbook -i inventories/single-ubuntu.ini playbooks/03_messy_setup.yml --syntax-check
ansible-playbook -i inventories/single-ubuntu.ini playbooks/05_intentional_failure_setup.yml --syntax-check
```

Safe dry run example:

```bash
ansible-playbook -i inventories/single-ubuntu.ini playbooks/01_simple_setup.yml --check --diff
```
