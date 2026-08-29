# Roteiro de Implantação e Testes — Servidor Web com HPA

Disciplina: PSI5120 — Tópicos de Computação em Nuvem
Autor: Ivo Motoki

## 1. Objetivo

Implantar o mesmo servidor web (imagem `registry.k8s.io/hpa-example`, o exemplo oficial de
HPA do Kubernetes) em dois clusters — Minikube (local) e AWS EKS (nuvem) — configurar o
Horizontal Pod Autoscaler em ambos, gerar carga controlada e registrar a evolução do número
de réplicas ao longo do tempo, para uma análise comparativa entre as duas implantações.

## 2. Pré-requisitos

- `kubectl`, `minikube`, `eksctl` e `aws` CLI instalados e configurados.
- Conta AWS com permissão para criar cluster EKS, node group (EC2), e Load Balancer.
- Docker (ou driver equivalente) disponível para o Minikube.

## 3. Implantação A — Minikube (local)

1. Executar `scripts/minikube_setup.sh` — cria o cluster, habilita o addon `metrics-server`
   e aplica `manifests/deployment.yaml`, `manifests/service.yaml`, `manifests/hpa.yaml`.
2. Confirmar que o metrics-server está funcional:
   ```
   kubectl --context hpa-2026 -n tf-hpa top pods
   ```
   (deve retornar uso de CPU/memória do pod `php-apache`, não erro).
3. **Evidência E1 (antes da carga):** capturar tela de `kubectl --context hpa-2026 -n tf-hpa get hpa,pods`
   mostrando `REPLICAS: 1` e `TARGETS: <alguns>%/50%`.
   Salvar como `evidencias/minikube/E1_antes_carga.png`.
4. Rodar `scripts/load_test.sh minikube hpa-2026` — sobe 6 pods geradores de carga por
   240s, monitora a cada 10s, remove os geradores e continua monitorando por mais 150s
   (retração). Timeline salva em `evidencias/minikube/hpa_timeline_<data>.log`.
5. Durante a execução, em outro terminal, deixar rodando e capturar telas de:
   - `kubectl --context hpa-2026 -n tf-hpa get hpa -w` (ver `TARGETS` subir e `REPLICAS` aumentar)
   - `kubectl --context hpa-2026 -n tf-hpa get pods -w` (novos pods sendo criados)
   **Evidência E2 (pico de carga):** `evidencias/minikube/E2_pico_carga.png`.
6. Após o fim da carga (script já espera a retração), capturar:
   **Evidência E3 (retração):** `evidencias/minikube/E3_retracao.png` — `REPLICAS` voltando a 1.
7. Ao terminar todos os testes: `scripts/cleanup.sh minikube` (apaga o perfil Minikube).

## 4. Implantação B — AWS EKS (nuvem)

> ⚠️ Cria recursos com custo real (control plane + 4× EC2 t3.micro). Confirmar antes de
> rodar e não deixar o cluster ativo além do tempo do experimento.

1. Confirmar identidade/conta AWS: `aws sts get-caller-identity`.
2. Executar `scripts/eks_setup.sh` — cria o cluster via `eks/cluster.yaml` (control plane +
   node group), aplica `manifests/deployment.yaml`, `manifests/service.yaml` (ClusterIP,
   necessário para o `load_test.sh` funcionar via DNS interno) e `manifests/hpa.yaml`, e
   adiciona `eks/service-loadbalancer.yaml` para acesso público. O EKS já instala o
   metrics-server automaticamente como addon gerenciado (não precisa do patch
   `--kubelet-insecure-tls` usado no Minikube).
3. Obter o DNS do Load Balancer: `kubectl -n tf-hpa get svc php-apache-lb`.
   **Evidência E0 (acesso externo):** capturar `curl http://<dns-do-lb>/` retornando a
   página do php-apache — comprova a implantação acessível externamente.
   Salvar como `evidencias/eks/E0_acesso_externo.png` (ou `.txt`, ver nota¹ na Seção 6).
4. Repetir os passos 3–6 da Seção 3 (evidências E1–E3), trocando o contexto para o do
   cluster EKS e usando `scripts/load_test.sh eks <contexto-eks> 240 360 3` (usar poucos
   geradores — ver nota sobre capacidade de pods por nó na Seção 6.2).
5. **Imediatamente após capturar as evidências**, rodar `scripts/cleanup.sh eks`:
   remove o Service LoadBalancer primeiro (evita LB órfão), depois `eksctl delete cluster`,
   e roda uma verificação somente-leitura para confirmar que nada ficou ativo.
6. Conferir manualmente no Console AWS (EC2 → Instâncias, EC2 → Load Balancers,
   CloudFormation → Stacks) que nada relacionado a `psi5120-tf-hpa-eks` permaneceu.

## 5. Dados a extrair de cada `hpa_timeline_*.log` para o artigo

- Tempo entre início da carga e a primeira réplica adicional (tempo de reação do HPA).
- Número máximo de réplicas atingido e em que momento.
- Tempo entre o fim da carga e o retorno a `minReplicas` (tempo de retração).
- Utilização de CPU (`TARGETS`) ao longo do tempo.

## 6. Checklist de evidências mínimas

| Cluster  | E0 (acesso externo) | E1 (antes) | E2 (pico) | E3 (retração) | timeline log |
|----------|:---:|:---:|:---:|:---:|:---:|
| Minikube | — | log¹ | log¹ | log¹ | ✅ `hpa_timeline_20260825_023826.log` |
| EKS      | ✅ `E0_acesso_externo.txt` | log¹ | log¹ | log¹ | ✅ `hpa_timeline_20260826_010657.log` |

¹ Nesta execução, automação de screenshot de janelas de Terminal se mostrou pouco
confiável (ver notas da sessão); os momentos antes/pico/retração foram registrados
via log de texto (`kubectl get hpa/pods/top` a cada 10s) em vez de capturas de tela.
Recomenda-se complementar com screenshots reais antes da entrega final, seguindo o
mesmo roteiro (rodar `load_test.sh` novamente e capturar manualmente nos momentos-chave).

### 6.1 Resultado observado — Implantação A (Minikube)

Ciclo completo do HPA sob carga (6 pods busybox em loop de wget, DNS interno):

| Momento | Hora | REPLICAS | TARGETS (cpu) |
|---|---|---|---|
| Antes da carga | 02:38:27 | 1 | 8% / 50% |
| Início do scale-up | 02:39:38 | 1 | 192% / 50% |
| 1º scale-up | 02:39:49 | 4 | 192% / 50% |
| Scale-up intermediário | 02:41:47 | 8 | 167% / 50% |
| Pico (máximo atingido) | 02:41:59 | 10 | 167% / 50% |
| Carga removida | 02:42:35 | 10 | 131% / 50% |
| CPU já baixa, ainda sem retração | 02:44:28 | 10 | 10% / 50% |
| Retração completa | 02:54:40 | 1 | 26% / 50% |

- **Tempo de reação (scale-up):** ~1min22s entre a carga atingir os pods (≈02:38:39) e o
  primeiro aumento de réplicas (02:39:49).
- **Tempo até o máximo:** ~2min10s da carga inicial até atingir 10 réplicas (limite `maxReplicas`).
- **Tempo de retração:** ~12min entre o fim da carga (02:42:35) e o retorno a 1 réplica
  (02:54:40) — consistente com a janela padrão de estabilização de downscale do HPA (5min),
  contada a partir da última leitura de alta utilização.

### 6.2 Resultado observado — Implantação B (AWS EKS)

Ciclo completo do HPA sob carga (3 pods busybox em loop de wget, DNS interno):

| Momento | Hora | REPLICAS | TARGETS (cpu) |
|---|---|---|---|
| Antes da carga | 01:06:57 | 1 | 8% / 50% |
| Início do scale-up | 01:07:31 | 1 | 116% / 50% |
| 1º scale-up | 01:07:48 | 3 | 248% / 50% |
| Pico (limitado por capacidade) | 01:08:05 | 5 | 185% / 50% |
| Carga removida | ~01:10:57 | 5 | — |
| CPU já baixa, ainda sem retração | 01:16:59 | 5 | 8% / 50% |
| Retração completa | 01:18:05 | 1 | 10% / 50% |

- **Tempo de reação (scale-up):** ~34s entre a carga atingir os pods (≈01:06:57) e o
  primeiro salto de utilização (116% às 01:07:31); primeira réplica extra às 01:07:48
  (~51s).
- **Teto real de réplicas:** o HPA tentou escalar além de 5 (CPU chegou a 250%/50%, bem
  acima do necessário para justificar mais réplicas), mas o cluster não tinha capacidade
  livre — ver nota sobre limite de pods por nó abaixo. Isso contrasta com o Minikube, que
  atingiu o `maxReplicas` configurado (10) sem restrição de capacidade.
- **Tempo de retração:** a janela de observação do `load_test.sh` (360s) quase capturou a
  retração mas terminou minutos antes; confirmada manualmente em 01:18:05, também
  consistente com a janela de estabilização de 5min do HPA.

**Limitação de capacidade encontrada (relevante para a comparação):** a conta AWS usada
(`Atv.1`, criada para uma atividade específica de outra aula) está restrita a instâncias
elegíveis para Free Tier — `t3.medium` foi rejeitado (`InvalidParameterCombination`), sendo
necessário usar `t3.micro`. Além do custo, `t3.micro` tem um limite rígido de **4 pods por
nó** (limite de IPs de ENI da VPC CNI, não de CPU/memória). Com os pods de sistema do EKS
(aws-node, kube-proxy, coredns, metrics-server) já ocupando a maior parte dessa capacidade,
o node group precisou ser ampliado de 2 para 4 nós só para conseguir agendar o
`php-apache` e observar algum escalonamento. Esse é um limite estrutural que **não existe
no Minikube** (onde a única restrição é a CPU/memória alocada ao cluster local) — um ponto
de comparação genuíno para a seção de análise do artigo (facilidade de gerenciamento vs.
restrições de um ambiente gratuito na nuvem).

**Nota operacional:** durante a implantação B, a resolução de DNS do `eksctl`/`kubectl`
(binários em Go) via o proxy de DNS do WSL2 mostrou-se instável, exigindo lógica de retry
nos scripts (`scripts/eks_setup.sh`) e, em um momento, desabilitar o `dnsTunneling` do
WSL2 via `.wslconfig`. Documentado aqui pois também é relevante para a seção de
"facilidade de gerenciamento" — parte da complexidade operacional observada teve origem no
ambiente local (WSL2), não na AWS em si.
