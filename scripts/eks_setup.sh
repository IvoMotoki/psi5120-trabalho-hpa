#!/usr/bin/env bash
# Implantacao B (nuvem): cria o cluster EKS via eksctl, instala o metrics-server
# (nao vem por padrao no EKS, diferente do addon do Minikube), aplica os mesmos
# manifestos base do Deployment/HPA e adiciona o Service LoadBalancer para acesso
# externo.
#
# ATENCAO: este script cria recursos que geram custo real na conta AWS (control
# plane do EKS + instancias EC2 do node group). Nao rodar sem confirmar antes.
#
# Uso: ./scripts/eks_setup.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="psi5120-tf-hpa-eks"
REGIAO="us-east-1"

# O resolvedor de DNS embutido do Go (usado por eksctl/kubectl) falha de forma
# intermitente contra o proxy de DNS sintetizado do WSL2 ("no such host" mesmo
# quando curl/ping funcionam), sem relacao com a AWS. Como o comando e idempotente
# nesta fase (nenhum recurso criado ainda), tentamos novamente algumas vezes.
retry() {
  local tentativas=5 i=1
  until "$@"; do
    if [[ $i -ge $tentativas ]]; then
      echo "Falhou apos $tentativas tentativas: $*" >&2
      return 1
    fi
    echo "Falha (tentativa $i/$tentativas), tentando de novo em 5s: $*" >&2
    sleep 5
    i=$((i + 1))
  done
}

echo "== Identidade AWS atual (confirme que e a conta esperada) =="
retry aws sts get-caller-identity

echo "== Criando cluster EKS (leva ~15-20 min): $CLUSTER =="
retry eksctl create cluster -f "$DIR/eks/cluster.yaml"

echo "== Apontando kubectl para o cluster =="
retry aws eks update-kubeconfig --region "$REGIAO" --name "$CLUSTER"

echo "== Instalando metrics-server (manifesto oficial upstream) =="
retry kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

echo "== Aplicando patch --kubelet-insecure-tls (necessario em alguns clusters eksctl) =="
echo "== ver manifests/metrics-server-patch.yaml para o motivo =="
retry kubectl patch deployment metrics-server -n kube-system --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

echo "== Aguardando metrics-server ficar pronto =="
retry kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s

echo "== Aplicando manifestos (deployment, hpa) e Service LoadBalancer =="
retry kubectl apply -f "$DIR/manifests/deployment.yaml"
retry kubectl apply -f "$DIR/manifests/hpa.yaml"
retry kubectl apply -f "$DIR/eks/service-loadbalancer.yaml"

echo "== Aguardando rollout do Deployment php-apache =="
retry kubectl -n tf-hpa rollout status deployment/php-apache --timeout=180s

echo "== Aguardando o Load Balancer receber um endereco (pode levar alguns minutos) =="
kubectl -n tf-hpa get svc php-apache-lb -w &
WATCH_PID=$!
sleep 90
kill "$WATCH_PID" 2>/dev/null || true

echo
echo "Pronto. Comandos uteis:"
echo "  kubectl -n tf-hpa get hpa -w"
echo "  kubectl -n tf-hpa get pods -w"
echo "  kubectl -n tf-hpa get svc php-apache-lb   # DNS publico do Load Balancer"
echo "  ./scripts/load_test.sh $CLUSTER"
echo
echo "LEMBRETE: ao terminar os testes, rode scripts/cleanup.sh eks para nao deixar"
echo "recursos cobrando (Service LoadBalancer, depois o cluster)."
