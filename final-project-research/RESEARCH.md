# Pesquisa para projeto final PSI5120 - extensao do trabalho de HPA

Data da pesquisa: 2026-09-06  
Base escolhida: opcao 2.2 do enunciado, estendendo o trabalho intermediario de HPA em Kubernetes/Minikube/AWS EKS.  
Entrega final da disciplina: 2026-09-27, 23h55.

## Decisao recomendada

O melhor caminho e transformar o trabalho intermediario de HPA em um artigo experimental mais completo sobre autoscaling em Kubernetes. A tese central recomendada e:

> O Horizontal Pod Autoscaler resolve apenas a escala da aplicacao; em um ambiente cloud gerenciado, o comportamento observado tambem depende da pipeline de metricas, da politica do HPA, da capacidade de agendamento, da densidade maxima de pods por no, do tipo de instancia, do autoscaling de nos e do custo operacional.

Titulo sugerido em ingles:

**Beyond CPU-Based Horizontal Pod Autoscaling: An Empirical Evaluation of Kubernetes Autoscaling Limits in Local Minikube and Managed AWS EKS Environments**

## Perguntas de pesquisa candidatas

RQ1. Com a mesma aplicacao e a mesma politica de HPA, como diferem tempo de reacao, pico de replicas e retracao entre Minikube e AWS EKS?

RQ2. Em EKS, quando o HPA recomenda mais replicas, quais limites externos ao HPA impedem que as replicas fiquem prontas?

RQ3. Como ajustes declarativos em `autoscaling/v2.behavior` alteram scale-up, scale-down e estabilidade quando comparados ao comportamento padrao?

RQ4. Qual e o impacto pratico de usar apenas CPU como metrica de autoscaling, em comparacao com extensoes baseadas em memoria, metricas customizadas ou eventos externos?

RQ5. Qual e o custo e a complexidade operacional para obter elasticidade "de verdade" em EKS, isto e, combinando HPA com node autoscaling?

## Fontes primarias e o que sustentam

### Kubernetes HPA

Fonte: Kubernetes, "Horizontal Pod Autoscaling"  
URL: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/

Achados:

- HPA e um controlador de loop periodico que ajusta replicas de workloads escalaveis, como Deployments e StatefulSets, para aproximar capacidade observada da demanda.
- O intervalo padrao do loop do controlador e 15 s, via `--horizontal-pod-autoscaler-sync-period`.
- Para CPU, a utilizacao depende de `resources.requests.cpu`; sem request relevante, a metrica do pod fica indefinida e o HPA nao consegue agir corretamente para essa metrica.
- A formula conceitual do HPA e baseada na razao entre metrica atual e metrica desejada: `desiredReplicas = ceil(currentReplicas * currentMetricValue / desiredMetricValue)`.
- Pods sem metricas ou ainda nao prontos sao tratados de forma especial no calculo, o que afeta resultados durante inicializacao.
- Quando ha multiplas metricas, o HPA calcula a recomendacao para cada uma e escolhe a maior contagem de replicas.
- O HPA pode usar resource metrics (`metrics.k8s.io`), custom metrics (`custom.metrics.k8s.io`) e external metrics (`external.metrics.k8s.io`).
- A janela padrao de estabilizacao de scale-down e 5 minutos, o que explica retracao lenta apos fim da carga.
- Desde Kubernetes v1.37, `minReplicas: 0` e beta e habilitado por padrao, mas apenas com metricas customizadas/externas, nao com CPU/memoria.

Uso no artigo:

- Fundamento teorico do algoritmo.
- Explicacao da assimetria entre scale-up e scale-down.
- Justificativa para medir tempo de reacao, tempo de estabilizacao e over/underprovisioning.
- Limitacao de escopo: CPU-only HPA nao cobre workloads orientados a fila/eventos.

### Kubernetes HPA API `autoscaling/v2`

Fonte: Kubernetes API Reference, "HorizontalPodAutoscaler v2"  
URL: https://kubernetes.io/docs/reference/kubernetes-api/autoscaling/horizontal-pod-autoscaler-v2/

Achados:

- `autoscaling/v2` permite configurar `behavior.scaleUp` e `behavior.scaleDown`.
- Sem configuracao explicita, scale-down usa janela de estabilizacao de 300 s.
- Sem configuracao explicita, scale-up nao usa estabilizacao e permite o maior entre dobrar o numero de pods ou adicionar ate 4 pods por janela.
- `policies`, `selectPolicy`, `stabilizationWindowSeconds` e `tolerance` permitem controlar agressividade e evitar oscilacao.

Uso no artigo:

- Base para um experimento adicional de baixo risco: comparar HPA padrao contra HPA customizado.
- Possivel contribuicao nova em relacao ao trabalho intermediario: "policy tuning".

### Kubernetes Metrics Server

Fonte: Kubernetes SIGs, "Metrics Server"  
URL: https://kubernetes-sigs.github.io/metrics-server/

Achados:

- Metrics Server e fonte eficiente e escalavel de metricas de recursos para pipelines nativos de autoscaling.
- Coleta metricas a cada 15 s.
- Suporta autoscaling horizontal baseado em CPU/memoria e tambem VPA.
- Nao deve ser usado como solucao de monitoramento geral, nem como fonte precisa para analise historica; para isso, recomenda-se solucao de monitoramento como Prometheus.

Uso no artigo:

- Separar "metricas para controle" de "metricas para observabilidade".
- Justificar adicionar Prometheus/Grafana ou pelo menos coleta estruturada dos logs como extensao metodologica.

### Amazon EKS HPA

Fonte: AWS, "Scale pod deployments with Horizontal Pod Autoscaler - Amazon EKS"  
URL: https://docs.aws.amazon.com/eks/latest/userguide/horizontal-pod-autoscaler.html

Achados:

- Em EKS, HPA e o recurso padrao do Kubernetes; nao precisa ser instalado separadamente.
- E necessario haver uma fonte de metricas, como Kubernetes Metrics Server.
- A propria pagina da AWS baseia seu teste no walkthrough oficial do Kubernetes, alinhado ao trabalho intermediario.

Uso no artigo:

- Justificar comparabilidade entre Minikube e EKS usando o mesmo workload `php-apache`.
- Mostrar que o comportamento diferente no EKS nao e uma "API diferente de HPA", mas efeito das camadas do ambiente cloud.

### Amazon VPC CNI e densidade de pods

Fonte: AWS EKS Best Practices, "Amazon VPC CNI"  
URL: https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html

Achados:

- No EKS com VPC CNI em modo padrao, cada pod recebe um endereco IP privado secundario.
- A quantidade de pods por instancia depende de quantas ENIs e quantos enderecos IP por ENI o tipo de instancia suporta.
- A densidade de pods e uma restricao alem de CPU/memoria.
- Formula documentada: `(number of network interfaces * (IP addresses per interface - 1)) + 2`.
- Pods de infraestrutura, como CoreDNS, Elastic Load Balancer controller e metrics-server, tambem consomem capacidade de pods.

Uso no artigo:

- Principal explicacao tecnica para o teto observado no EKS com `t3.micro`.
- Excelente diferenca entre "maxReplicas configurado" e "replicas efetivamente agendaveis".

### Amazon EC2 T3

Fonte: AWS, "Amazon EC2 T3 Instances"  
URL: https://aws.amazon.com/ec2/instance-types/t3/

Achados:

- `t3.micro` tem 2 vCPUs, 1 GiB de memoria, baseline de 10% por vCPU e 12 CPU credits por hora.
- Preco on-demand Linux/Unix em US East/N. Virginia listado como US$0.0104/h.
- Por ser burstable, um experimento longo ou repetido pode ser afetado por creditos de CPU, nao apenas por vCPU nominal.

Uso no artigo:

- Analisar a escolha de instancia como variavel experimental.
- Discutir risco de confundir "2 vCPUs" com capacidade sustentada.

### Amazon EKS pricing

Fonte: AWS, "Amazon EKS Pricing"  
URL: https://aws.amazon.com/eks/pricing/

Achados:

- Clusters EKS sob suporte padrao custam US$0.10 por cluster-hora.
- Recursos usados por worker nodes, como EC2, EBS, IPv4 publico e trafego cross-AZ, sao cobrados separadamente.
- EKS Auto Mode tem cobranca adicional ao custo EC2.
- Fargate for EKS e cobrado por vCPU/memoria solicitados, do download da imagem ate encerramento do pod, com minimo de 1 minuto.

Uso no artigo:

- Transformar a secao de custo em estimativa auditavel.
- Comparar "custo direto zero" do Minikube com custo minimo inevitavel do control plane EKS.

### EKS node autoscaling

Fonte: AWS, "Scale cluster compute with Karpenter and Cluster Autoscaler"  
URL: https://docs.aws.amazon.com/eks/latest/userguide/autoscaling.html

Achados:

- EKS Auto Mode cria nos quando pods nao cabem nos existentes e consolida/remove nos subutilizados.
- AWS apresenta Karpenter e Cluster Autoscaler como alternativas de autoscaling de compute.
- Karpenter provisiona recursos EC2 "right-sized" em resposta a carga e requisitos dos pods, em menos de um minuto segundo a documentacao.
- Karpenter e open source e gerenciado pelo cliente quando instalado no cluster.

Uso no artigo:

- Diferenciar HPA (replicas de pods) de node autoscaling (capacidade do cluster).
- Propor, como extensao principal ou trabalho futuro, teste HPA + node autoscaling.

### KEDA

Fonte: KEDA, "Scaling Deployments, StatefulSets & Custom Resources"  
URL: https://keda.sh/docs/2.20/concepts/scaling-deployments/

Achados:

- KEDA monitora fontes de eventos e alimenta metricas para Kubernetes/HPA.
- Com KEDA, e possivel escalar workloads orientados a eventos, como filas Kafka/RabbitMQ/SQS, inclusive de 0 para N.
- KEDA separa fase de ativacao, que escala de/para zero, e fase de scaling, em que o HPA controla 1 para N.
- Workloads longos exigem cuidado porque o HPA pode terminar replicas durante scale-down sem conhecer progresso interno do processamento.

Uso no artigo:

- Nao recomendado como experimento obrigatorio pelo prazo, mas e otimo para discussao/future work.
- Pode virar mini-extensao se usarmos SQS + KEDA em Minikube ou EKS, mas isso aumenta escopo.

### Literatura academica

Fonte: Buzato and Goldman, "Extended version of Microservices Performance Optimization Through Horizontal Pod Autoscaling: A Comprehensive Study", International Journal of Networking and Computing, 2026.  
URL: https://www.jstage.jst.go.jp/article/ijnc/16/1/16_52/_article/-char/en  
DOI: https://doi.org/10.15803/ijnc.16.1_52

Achados:

- Estudo aberto e recente sobre HPA em arquiteturas de microservicos.
- Avalia desempenho, utilizacao de recursos e custos operacionais.
- Usa benchmark Sock-Shop e diferentes cenarios de carga.
- Relata trade-offs: melhora de throughput/latencia, mas com aumento de uso de disco e complexidade operacional.

Uso no artigo:

- Referencia academica forte e proxima do tema.
- Ajuda a justificar metricas de desempenho, custo e complexidade, mesmo que nosso workload seja mais simples.

Fonte: Jeong and Jeong, "Autoscaling techniques in cloud-native computing: A comprehensive survey", Computer Science Review, 2025.  
URL: https://www.sciencedirect.com/science/article/pii/S157401372500067X

Achados:

- Classifica autoscaling em horizontal, vertical e hibrido; e mecanismos reativos, proativos e hibridos.
- Destaca que autoscaling envolve desempenho, custo, continuidade de servico, oscilacao, atraso de scaling, underprovisioning, overprovisioning e ate ataques que exploram gatilhos de scaling.

Uso no artigo:

- Referencia para posicionar o HPA CPU-based como autoscaling horizontal reativo.
- Boa fonte para justificar discutir limites, custo e seguranca como dimensoes alem de replica count.

Fonte: Jiang and Wu, "A Fine-Grained Horizontal Scaling Method for Container-Based Cloud", Scientific Programming, 2021.  
URL: https://onlinelibrary.wiley.com/doi/10.1155/2021/6397786  
DOI: https://doi.org/10.1155/2021/6397786

Achados:

- Discute limitacoes do HPA diante de picos subitos, atraso de resposta e mecanismo anti-jitter.
- Propoe thresholds e graus de scaling mais finos, considerando tambem taxa de crescimento de CPU.

Uso no artigo:

- Fundamentar por que testar `behavior` do HPA e interessante: a literatura ja aponta que politica padrao pode ser lenta ou conservadora para certos picos.

## Opcoes de extensao avaliadas

### Opcao A - HPA behavior tuning

Resumo: repetir o experimento atual com duas ou tres politicas HPA:

1. Baseline: HPA atual, sem `behavior`.
2. Aggressive scale-up: permitir adicao mais rapida de pods.
3. Conservative/fast scale-down: alterar `stabilizationWindowSeconds` para reduzir ou aumentar retracao.

Exemplo de manifesto experimental:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: php-apache
  namespace: tf-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  minReplicas: 1
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Pods
          value: 6
          periodSeconds: 30
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 120
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
      selectPolicy: Max
```

Metricas:

- time-to-first-scale-up;
- time-to-max-replicas;
- time-to-scale-down;
- numero de mudancas de replicas;
- replica-seconds como proxy de custo/overprovisioning;
- tempo com CPU acima do alvo como proxy de underprovisioning.

Valor cientifico: alto.  
Risco: baixo.  
Custo AWS: baixo, pois pode ser feito primeiro no Minikube e opcionalmente no EKS.  
Recomendacao: fazer.

### Opcao B - Capacidade de agendamento no EKS

Resumo: documentar e, se possivel, repetir um teste curto variando a infraestrutura:

1. EKS com `t3.micro` atual: observar pods `Pending` e teto efetivo.
2. EKS com instancia maior, se a conta permitir, como `t3.small`, `t3.medium` ou `t3.large`.
3. Alternativa sem novo custo: calcular capacidade teorica usando formula da VPC CNI e evidencias existentes de `kubectl describe pod/node`.

Comandos de evidencia:

```bash
kubectl -n tf-hpa get pods -o wide
kubectl -n tf-hpa describe pod <pending-pod>
kubectl get nodes -o wide
kubectl describe node <node>
kubectl get daemonset -A
kubectl get pods -A -o wide
```

Metricas:

- `maxReplicas` configurado vs replicas agendadas;
- pods em `Pending`;
- razoes do scheduler;
- capacidade de pods por no;
- pods de sistema consumindo slots.

Valor cientifico: muito alto, porque foi o achado mais interessante do trabalho intermediario.  
Risco: medio se depender de AWS; baixo se virar analise documentada com evidencias existentes.  
Custo AWS: medio se criar novo EKS; zero se usar logs/evidencias existentes.  
Recomendacao: fazer pelo menos como analise; repetir so se houver credito/tempo.

### Opcao C - HPA + node autoscaling

Resumo: adicionar Cluster Autoscaler, Karpenter ou EKS Auto Mode para testar se o cluster cria nos quando o HPA gera pods que nao cabem.

Experimento ideal:

1. Configurar node group com capacidade inicial pequena.
2. Gerar carga.
3. HPA aumenta replicas.
4. Scheduler deixa pods pendentes.
5. Node autoscaler adiciona nos.
6. Pods pendentes passam para Running.
7. Apos carga, replicas e nos diminuem.

Metricas:

- tempo HPA ate criar pods;
- tempo scheduler ate marcar `Pending`;
- tempo node autoscaler ate novo no `Ready`;
- tempo total ate capacidade efetiva;
- custo por duracao.

Valor cientifico: muito alto.  
Risco: alto para o prazo, pois exige EKS, IAM, node groups/autoscaler e limpeza cuidadosa.  
Custo AWS: maior.  
Recomendacao: deixar como experimento opcional ou trabalho futuro, salvo se houver um dia livre so para isso.

### Opcao D - Observabilidade com Prometheus/Grafana

Resumo: adicionar coleta melhor de metricas no Minikube com Prometheus/Grafana ou kube-prometheus-stack, sem depender de AWS.

Metricas:

- CPU por pod;
- replica count ao longo do tempo;
- requisicoes por segundo;
- latencia HTTP se trocar gerador para `hey`, `wrk` ou `k6`;
- consumo por no.

Valor cientifico: medio-alto.  
Risco: medio, por instalacao e troubleshooting.  
Custo AWS: zero se local.  
Recomendacao: fazer apenas se quisermos graficos melhores; nao e obrigatorio se os logs atuais forem suficientes.

### Opcao E - Workload mais realista

Resumo: trocar ou complementar `php-apache` por um servico simples proprio que exponha endpoints CPU-bound e I/O-bound, com controle de intensidade.

Exemplo:

- `/cpu?n=...` executa loop computacional;
- `/sleep?ms=...` simula latencia I/O;
- `/healthz` para probes;
- container com requests/limits configuraveis.

Valor cientifico: medio.  
Risco: medio.  
Custo AWS: baixo/local.  
Recomendacao: nao priorizar, porque o workload oficial tem a vantagem de ser reprodutivel e citado pela documentacao.

### Opcao F - Metricas externas ou KEDA

Resumo: escalar com base em fila/evento, por exemplo SQS queue depth.

Valor cientifico: alto, mas foge bastante do trabalho atual.  
Risco: alto.  
Custo AWS: medio.  
Recomendacao: mencionar em discussao/future work; executar apenas se sobrar tempo.

## Plano recomendado de projeto final

### Escopo final enxuto e forte

Manter o objeto de estudo:

- Kubernetes HPA;
- Minikube local;
- AWS EKS gerenciado;
- workload `php-apache` oficial;
- metrica CPU via Metrics Server;
- geracao de carga interna por pods.

Adicionar:

1. experimento de tuning do `behavior` do HPA no Minikube;
2. analise mais forte do limite de pods por no no EKS;
3. metricas derivadas dos logs: reaction time, time-to-peak, time-to-scale-down, replica-seconds, underprovisioning window;
4. discussao sobre HPA vs node autoscaling;
5. discussao sobre custo EKS/EC2/Load Balancer;
6. related work academico com HPA/microservicos/autoscaling cloud-native.

### Experimentos minimos necessarios

Experimento 1 - baseline Minikube:

- Reusar logs existentes.
- Se quiser melhorar confianca, repetir 3 vezes localmente.
- Extrair serie temporal de replicas e CPU.

Experimento 2 - HPA behavior Minikube:

- Criar `manifests/hpa-aggressive.yaml`.
- Rodar o mesmo `scripts/load_test.sh`.
- Comparar com baseline.

Experimento 3 - EKS infraestrutura:

- Usar logs existentes para mostrar teto de replicas.
- Complementar com fonte AWS sobre VPC CNI/max pods.
- Opcional: novo teste curto em EKS se houver tempo/credito.

Experimento 4 - custo:

- Atualizar estimativa com precos oficiais de EKS, EC2 T3 e ELB.
- Calcular custo por hora e custo do experimento.

## Como transformar em artigo IEEE

### Titulo recomendado

**Beyond CPU-Based Horizontal Pod Autoscaling: Empirical Limits of Kubernetes Autoscaling in Local and Managed Cloud Environments**

### Abstract

Uma versao forte deve afirmar:

- o trabalho compara HPA em Minikube e EKS;
- usa mesmo workload e mesma carga;
- mede tempo de reacao, pico, retracao e restricoes de capacidade;
- mostra que HPA escala replicas, mas nao garante capacidade se o cluster nao consegue agendar pods;
- discute custo e extensoes com behavior tuning/node autoscaling.

### Secoes

1. Introduction
2. Background: Kubernetes HPA and Metrics Pipeline
3. Related Work
4. Experimental Setup
5. Baseline Evaluation: Minikube vs EKS
6. Extension 1: HPA Behavior Tuning
7. Extension 2: Cloud Infrastructure Constraints in EKS
8. Cost and Operational Discussion
9. Threats to Validity
10. Conclusion

### Figuras/tabelas recomendadas

- Arquitetura: workload, Service, Metrics Server, HPA controller, Deployment, pods, node capacity.
- Linha do tempo Minikube baseline.
- Linha do tempo EKS baseline.
- Comparativo baseline vs tuned HPA.
- Tabela de custos.
- Tabela `configured maxReplicas` vs `effective schedulable replicas`.

## Decisao de prioridade

Prioridade 1: extrair metricas quantitativas dos logs existentes.  
Prioridade 2: criar e rodar HPA behavior tuning local.  
Prioridade 3: escrever analise EKS com VPC CNI/maxPods.  
Prioridade 4: atualizar artigo para IEEE em ingles.  
Prioridade 5: experimento novo em EKS somente se custo/tempo permitirem.

## Riscos

- Criar EKS novo pode consumir tempo e dinheiro. Mitigacao: usar evidencias existentes e fazer extensoes no Minikube.
- KEDA/Prometheus/Karpenter podem virar escopo demais. Mitigacao: tratar como discussao ou future work.
- O artigo precisa ser IEEE, enquanto o intermediario usa template SBC. Mitigacao: migrar cedo para IEEEtran.
- O trabalho final exige minimo de 6 paginas; com related work, metodologia, resultados, extensao de behavior e discussao de custo, 8-10 paginas e realista.

## Proxima acao recomendada

Criar uma pasta `7. Trabalho HPA/final-ieee/` com:

- `main.tex` em IEEEtran;
- `references.bib`;
- `figures/`;
- `data/` com CSVs extraidos dos logs;
- `scripts/parse_hpa_timeline.py`;
- `manifests/hpa-aggressive.yaml`;
- `manifests/hpa-conservative.yaml`.

Depois, gerar automaticamente tabelas e graficos a partir dos logs existentes antes de escrever o artigo final.
