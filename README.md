# Servidor Web com Horizontal Pod Autoscaler — Minikube + AWS EKS

Trabalho da disciplina **PSI5120 — Tópicos de Computação em Nuvem**. Projeta, implanta e
testa um servidor web em Kubernetes com autoescalamento horizontal de pods (HPA), em duas
implantações: local (Minikube) e em nuvem (AWS EKS gerenciado).

## Estrutura

```
manifests/    Deployment, Service (ClusterIP) e HPA — usados em ambas as implantações
eks/          Definição do cluster eksctl e Service LoadBalancer, específicos do EKS
scripts/      Automação: setup dos clusters, geração de carga, limpeza
roteiro/      Roteiro passo a passo de implantação e testes (ROTEIRO.md)
evidencias/   Screenshots e logs de timeline do HPA, por cluster
artigo/       Artigo científico em LaTeX (template oficial SBC)
```

## Como reproduzir

Ver [roteiro/ROTEIRO.md](roteiro/ROTEIRO.md) para o passo a passo completo. Resumo:

```bash
# Implantação A — Minikube
./scripts/minikube_setup.sh
./scripts/load_test.sh minikube hpa-2026
./scripts/cleanup.sh minikube

# Implantação B — AWS EKS (gera custo real — ver aviso no script)
./scripts/eks_setup.sh
./scripts/load_test.sh eks psi5120-tf-hpa-eks
./scripts/cleanup.sh eks
```

## Aplicação alvo

Ambas as implantações usam a imagem `registry.k8s.io/hpa-example` (exemplo oficial do
walkthrough de HPA do Kubernetes), um servidor PHP/Apache com um endpoint que realiza
cálculo intensivo de CPU sob demanda — permite gerar carga controlada e observar o
autoescalamento de forma previsível e comparável entre os dois clusters.

## Resultados

Ver o artigo em [artigo/trabalho_hpa_psi5120_ivo_motoki.tex](artigo/trabalho_hpa_psi5120_ivo_motoki.tex)
para a análise comparativa completa entre as duas implantações.

## Autor

Ivo Motoki — PSI5120, Escola Politécnica (USP)
