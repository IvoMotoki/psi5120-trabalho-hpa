#!/usr/bin/env bash
# Limpeza dos recursos criados neste trabalho, evitando custo residual.
# Uso: ./scripts/cleanup.sh minikube
#      ./scripts/cleanup.sh eks
set -euo pipefail

ALVO="${1:?Uso: cleanup.sh <minikube|eks>}"

if [[ "$ALVO" == "minikube" ]]; then
  PERFIL="${PERFIL:-hpa-2026}"
  echo "== Excluindo perfil Minikube: $PERFIL =="
  minikube delete -p "$PERFIL"
  echo "== Perfis Minikube restantes (confirme que $PERFIL nao aparece mais) =="
  minikube profile list || true
  exit 0
fi

if [[ "$ALVO" == "eks" ]]; then
  CLUSTER="psi5120-tf-hpa-eks"
  REGIAO="us-east-1"

  echo "== Excluindo Service LoadBalancer primeiro (evita CLB orfao) =="
  kubectl -n tf-hpa delete svc php-apache-lb --ignore-not-found

  echo "== Aguardando 60s para a AWS liberar o Load Balancer associado =="
  sleep 60

  echo "== Excluindo o cluster EKS: $CLUSTER (pode levar ~10 min) =="
  eksctl delete cluster --name "$CLUSTER" --region "$REGIAO"

  echo
  echo "== Verificacao pos-limpeza (somente leitura, nao apaga nada) =="
  echo "Cluster EKS:"
  aws eks describe-cluster --region "$REGIAO" --name "$CLUSTER" \
    --query 'cluster.{name:name,status:status}' --output table 2>&1 || echo "  (nao encontrado - OK)"

  echo "Classic Load Balancers restantes:"
  aws elb describe-load-balancers --region "$REGIAO" \
    --query 'LoadBalancerDescriptions[].{name:LoadBalancerName,dns:DNSName}' --output table || true

  echo "Load Balancers v2 (ALB/NLB) restantes:"
  aws elbv2 describe-load-balancers --region "$REGIAO" \
    --query 'LoadBalancers[].{name:LoadBalancerName,type:Type,state:State.Code}' --output table || true

  echo
  echo "Confira tambem no Console AWS (EC2 > Instancias, EC2 > Load Balancers,"
  echo "CloudFormation > Stacks) que nada relacionado a '$CLUSTER' permaneceu ativo."
  exit 0
fi

echo "Primeiro argumento deve ser 'minikube' ou 'eks'." >&2
exit 1
