# Reproduction container for the analysis chain. Draw-file byte-identity for
# the bootstrap is guaranteed only inside this container (fixed BLAS and
# single-threaded execution); outside it, expect statistical agreement.
FROM python:3.10.12-slim
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1
WORKDIR /work
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
CMD ["bash", "-c", "python3 sweep/recompute_from_raw.py && python3 sweep/refit_exponents.py && python3 sweep/make_figures.py && python3 sweep/prose_numbers.py && python3 sweep/test_pipeline.py"]
