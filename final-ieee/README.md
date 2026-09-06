# PSI5120 final project - HPA extension

This directory contains the final-project extension of the intermediate HPA work.
The goal is to turn the original Minikube vs AWS EKS experiment into an IEEE-style
paper about practical limits of Kubernetes autoscaling.

## Structure

- `main.tex`: IEEE article draft.
- `references.bib`: bibliography for official docs and related work.
- `scripts/parse_hpa_timeline.py`: parser for raw `kubectl get hpa/get pods/top pods` logs.
- `data/`: generated CSV files and summary tables.
- `manifests/`: HPA variants used in the additional behavior-tuning experiment.
- `figures/`: generated figures for the article.

## Generate data from existing logs

From `7. Trabalho HPA`:

```bash
python final-ieee/scripts/parse_hpa_timeline.py
```

The script reads `evidencias/minikube/*.log` and `evidencias/eks/*.log`, then writes
per-run CSV files and `final-ieee/data/summary.csv`.

Generate PNG figures from those CSV files:

```bash
python final-ieee/scripts/plot_hpa_timeline.py
```

Check that cited BibTeX keys exist:

```bash
python final-ieee/scripts/check_tex_refs.py
```

## Recommended next experiment

Run the same load-test script locally with each HPA variant:

```bash
kubectl apply -f manifests/deployment.yaml
kubectl apply -f manifests/service.yaml

kubectl apply -f final-ieee/manifests/hpa-baseline.yaml
./scripts/load_test.sh minikube hpa-2026 240 720 6

kubectl apply -f final-ieee/manifests/hpa-aggressive.yaml
./scripts/load_test.sh minikube hpa-2026 240 720 6

kubectl apply -f final-ieee/manifests/hpa-fast-scaledown.yaml
./scripts/load_test.sh minikube hpa-2026 240 720 6
```

Use a 720 s post-load window so the downscale behavior is captured reliably.
