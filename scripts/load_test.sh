#!/usr/bin/env bash
# Gera carga de CPU contra o Service php-apache (ClusterIP) DE DENTRO do cluster,
# usando N pods busybox em loop de wget - a mesma tecnica do walkthrough oficial do
# HPA (Referencia 1 do enunciado), com varios pods em paralelo para gerar carga
# suficiente para acionar o autoescalamento de forma confiavel.
#
# Usar o DNS interno do cluster (nao um endereco externo) garante que o MESMO
# metodo de teste seja usado tanto no Minikube quanto no EKS, o que e necessario
# para a comparacao pedida no enunciado.
#
# Durante e depois da carga, o script registra um "timeline" (hpa + pods + top)
# em um arquivo de log, usado depois para escrever a analise comparativa no artigo.
#
# Uso: ./scripts/load_test.sh <minikube|eks> [context] [duracao_carga_s] [duracao_pos_s] [geradores]
set -euo pipefail

ALVO="${1:?Uso: load_test.sh <minikube|eks> [context] [duracao_carga_s] [duracao_pos_s] [geradores]}"
CONTEXT="${2:-}"
DURACAO_CARGA="${3:-240}"
# 360s (6min): o HPA usa por padrao uma janela de estabilizacao de downscale de 5min
# (--horizontal-pod-autoscaler-downscale-stabilization) antes de retrair replicas,
# confirmado empiricamente na Implantacao A - uma janela menor nao captura a retracao.
DURACAO_POS="${4:-360}"
GERADORES="${5:-6}"

if [[ "$ALVO" != "minikube" && "$ALVO" != "eks" ]]; then
  echo "Primeiro argumento deve ser 'minikube' ou 'eks'." >&2
  exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVID_DIR="$DIR/evidencias/$ALVO"
mkdir -p "$EVID_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$EVID_DIR/hpa_timeline_${TIMESTAMP}.log"

KCTX=()
if [[ -n "$CONTEXT" ]]; then
  KCTX=(--context "$CONTEXT")
fi

echo "== Alvo: $ALVO | contexto: ${CONTEXT:-<atual>} | log: $LOG =="

echo "== Subindo $GERADORES geradores de carga (busybox, wget em loop) =="
kubectl "${KCTX[@]}" -n tf-hpa create deployment load-generator \
  --image=busybox --replicas="$GERADORES" \
  -- /bin/sh -c "while true; do wget -q -O- http://php-apache.tf-hpa.svc.cluster.local; done"

registrar() {
  {
    echo "---- $(date '+%Y-%m-%d %H:%M:%S') ----"
    kubectl "${KCTX[@]}" -n tf-hpa get hpa
    kubectl "${KCTX[@]}" -n tf-hpa get pods -o wide
    kubectl "${KCTX[@]}" -n tf-hpa top pods 2>/dev/null || echo "(metrics ainda nao disponiveis)"
    echo
  } >> "$LOG"
}

echo "== Fase 1/2: monitorando por ${DURACAO_CARGA}s com carga ativa (registro a cada 10s) =="
FIM=$(( $(date +%s) + DURACAO_CARGA ))
while [[ $(date +%s) -lt $FIM ]]; do
  registrar
  sleep 10
done

echo "== Removendo geradores de carga =="
kubectl "${KCTX[@]}" -n tf-hpa delete deployment load-generator

echo "== Fase 2/2: monitorando retracao por ${DURACAO_POS}s (sem carga, registro a cada 10s) =="
FIM=$(( $(date +%s) + DURACAO_POS ))
while [[ $(date +%s) -lt $FIM ]]; do
  registrar
  sleep 10
done

echo
echo "Timeline completa salva em: $LOG"
echo "Use esse arquivo para extrair o numero de replicas ao longo do tempo e o"
echo "tempo de reacao do HPA para o artigo. Tire tambem screenshots de momentos-chave"
echo "(kubectl get hpa -w / get pods -w rodando ao vivo) para evidencias/$ALVO/."
