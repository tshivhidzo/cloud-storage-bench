# Reproduction container: the byte-reproducibility boundary for the bootstrap
# draw file. Base pinned by multi-arch manifest digest (python:3.10.12-slim).
FROM python@sha256:4d440b214e447deddc0a94de23a3d97d28dfafdf125a8b4bb8073381510c9ee2
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1
WORKDIR /work
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
# Default: regenerate the ENTIRE chain INCLUDING all five bootstrap batches
# from scratch, then verify the regenerated draw file's SHA-256 against the
# committed one, then run the regression tests.
CMD ["bash", "sweep/container_verify.sh"]
