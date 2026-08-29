#!/usr/bin/env bash
# Implantacao A (local): cria/inicia um perfil Minikube dedicado a este trabalho,
# habilita o metrics-server (necessario para o HPA calcular utilizacao de CPU) e
# aplica os manifestos base (namespace, deployment, service, hpa).
#
# Uso: ./scripts/minikube_setup.sh
set -euo pipefail

PERFIL="${PERFIL:-hpa-2026}"
CPUS="${CPUS:-4}"
MEMORIA="${MEMORIA:-6144}"

# Diretorio do projeto (independente de onde o script for chamado a partir dele)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Criando/iniciando cluster Minikube (perfil: $PERFIL) =="
minikube start -p "$PERFIL" --cpus "$CPUS" --memory "$MEMORIA"

echo "== Habilitando addon metrics-server =="
minikube addons enable metrics-server -p "$PERFIL"

echo "== Aguardando metrics-server ficar pronto =="
kubectl --context "$PERFIL" -n kube-system rollout status deployment/metrics-server --timeout=240s

echo "== Aplicando manifestos (namespace, deployment, service, hpa) =="
kubectl --context "$PERFIL" apply -f "$DIR/manifests/deployment.yaml"
kubectl --context "$PERFIL" apply -f "$DIR/manifests/service.yaml"
kubectl --context "$PERFIL" apply -f "$DIR/manifests/hpa.yaml"

echo "== Aguardando rollout do Deployment php-apache =="
kubectl --context "$PERFIL" -n tf-hpa rollout status deployment/php-apache --timeout=240s

echo
echo "Pronto. Comandos uteis para observar o experimento:"
echo "  kubectl --context $PERFIL -n tf-hpa get hpa -w"
echo "  kubectl --context $PERFIL -n tf-hpa get pods -w"
echo "  kubectl --context $PERFIL -n tf-hpa top pods"
echo
echo "O Service e ClusterIP (sem endereco externo no cluster local). A geracao de carga"
echo "e feita de DENTRO do cluster por scripts/load_test.sh, que ja resolve o servico"
echo "pelo DNS interno (php-apache.tf-hpa.svc.cluster.local) - nenhum port-forward necessario."
echo "  ./scripts/load_test.sh $PERFIL"
