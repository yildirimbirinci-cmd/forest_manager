# Stage 4O - Offline Model Bootstrap

Forest Manager runtime remains fully local.

The only network operation in this stage is a one-time DEVELOPMENT bootstrap to
obtain the approved model files that will later be bundled inside the final
Forest Manager installer.

Approved model:

    HuggingFaceTB/SmolVLM-500M-Instruct

Pinned revision:

    e2d212496dbdaa5d0e540b14645c2a0a77eece6e

The bootstrap explicitly excludes the repository's ONNX directory and downloads
only the Transformers runtime files. The main model weight is approximately
1.02 GB.

Expected model.safetensors SHA256:

    d05b567eeaf534e83d375551f068ed57b5f52d37c657197f644af5ef9db091a2

## One-time developer bootstrap

From the Forest Manager repository root:

    python tools/bootstrap_smolvlm_model.py

No API key is required for this public model.

## Verify

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.local_model_stage4o_verify

Expected after a successful bootstrap:

    Stage 4O offline model verification passed.

## Runtime policy

After bootstrap:

- disconnecting the internet must not affect inference,
- HF_HUB_OFFLINE=1 is forced,
- TRANSFORMERS_OFFLINE=1 is forced,
- local_files_only=True is forced,
- there is no cloud fallback.

The final installer will carry these approved model files, so end users will not
run the bootstrap command.
