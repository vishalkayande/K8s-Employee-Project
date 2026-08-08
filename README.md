# Kubernetes Live Project: Employee Directory (Python + MySQL + Redis)

A KodeKloud-style hands-on lab. You will containerize a Python Flask app
and deploy it to Kubernetes alongside a MySQL pod (persistent storage) and
a Redis pod (cache + counter), wiring them together with Services,
ConfigMaps, Secrets, a PVC, init containers, and health probes.

## Architecture

```
                    ┌─────────────────────────┐
   Browser ───────▶ │  Service: employee-app  │  (NodePort 30080)
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Deployment:             │
                    │  employee-app (2 pods)   │
                    │  Flask + Gunicorn        │
                    └──────┬────────────┬──────┘
                           │            │
              ┌────────────▼──┐   ┌─────▼───────────┐
              │ Service: mysql │   │ Service: redis   │
              └────────┬───────┘   └────────┬─────────┘
                       │                     │
              ┌────────▼───────┐   ┌─────────▼────────┐
              │ Deployment:    │   │ Deployment:       │
              │ mysql (1 pod)  │   │ redis (1 pod)     │
              │ + PVC storage  │   │ in-memory         │
              └────────────────┘   └───────────────────┘
```

- **MySQL** stores employee records permanently (PVC-backed).
- **Redis** caches the employee list for 30 seconds and keeps a live
  page-view counter — proof the app is genuinely using two independent
  backends, not just one.
- The Flask app exposes `/health` (liveness) and `/ready` (readiness,
  checks both DB connections) so probes have something real to test.

## What's in this repo

```
app/                     Flask application source
  app.py
  requirements.txt
  Dockerfile
  templates/              Bootstrap-based UI
  static/style.css
k8s/                      Kubernetes manifests, applied in numeric order
  00-namespace.yaml
  01-secrets.yaml
  02-configmap.yaml
  03-mysql-pvc.yaml
  04-mysql-deployment.yaml
  05-mysql-service.yaml
  06-redis-deployment.yaml
  07-redis-service.yaml
  08-app-deployment.yaml
  09-app-service.yaml
```

## Prerequisites

- A working Kubernetes cluster (minikube, kind, or a real cluster)
- `kubectl` configured against that cluster
- Docker (or another builder) to build the app image
- A container registry the cluster can pull from — Docker Hub is fine,
  or `minikube image load` / `kind load docker-image` for local clusters

---

## Student Tasks

### Task 1 — Build and load the application image
1. `cd app/`
2. Build the image: `docker build -t employee-app:1.0.0 .`
3. Make it available to your cluster:
   - minikube: `minikube image load employee-app:1.0.0`
   - kind: `kind load docker-image employee-app:1.0.0`
   - real cluster: tag and push to your registry, then update the
     `image:` field in `k8s/08-app-deployment.yaml` accordingly.

### Task 2 — Review the Secret and ConfigMap
Open `k8s/01-secrets.yaml` and `k8s/02-configmap.yaml`. Decode a secret
value to prove to yourself it's just base64:
```
echo 'YXBwdXNlcg==' | base64 -d
```
Question to answer: why is a Secret still not "secure" by itself in a
default cluster install? (Hint: research RBAC and etcd encryption at rest.)

### Task 3 — Deploy MySQL
Apply, in order:
```
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmap.yaml
kubectl apply -f k8s/03-mysql-pvc.yaml
kubectl apply -f k8s/04-mysql-deployment.yaml
kubectl apply -f k8s/05-mysql-service.yaml
```
Verify: `kubectl get pods -n emp-directory -w` until MySQL is `Running`
and `1/1 Ready`. Check the PVC is `Bound`: `kubectl get pvc -n emp-directory`.

### Task 4 — Deploy Redis
```
kubectl apply -f k8s/06-redis-deployment.yaml
kubectl apply -f k8s/07-redis-service.yaml
```
Verify it responds: `kubectl exec -n emp-directory deploy/redis -- redis-cli ping`

### Task 5 — Deploy the application
```
kubectl apply -f k8s/08-app-deployment.yaml
kubectl apply -f k8s/09-app-service.yaml
```
Watch the init containers do their job:
```
kubectl get pods -n emp-directory
kubectl logs -n emp-directory <app-pod-name> -c wait-for-mysql
```
Once both app pods are Ready, access the UI:
- minikube: `minikube service employee-app -n emp-directory --url`
- otherwise: `http://<any-node-ip>:30080`

### Task 6 — Prove both backends are in play
1. Add a couple of employees through the UI.
2. Refresh the page rapidly — watch the "Data Source" badge switch
   between **MySQL (fresh)** and **Redis Cache**.
3. Delete `mysql` pod (`kubectl delete pod -n emp-directory -l app=mysql`)
   and watch it get recreated by the Deployment — your data should
   still be there afterward (thanks to the PVC). Confirm in the UI.
4. Delete the `redis` pod and confirm the app keeps working (falls back
   to MySQL) — this demonstrates Redis is a cache, not a source of truth.

### Task 7 — Break something on purpose
1. Scale MySQL to 0: `kubectl scale deploy/mysql -n emp-directory --replicas=0`
2. Hit `/ready` on the app (`kubectl port-forward` or via the NodePort) —
   it should now report `mysql: down` and return HTTP 503.
3. Scale MySQL back up and confirm recovery.

### Task 8 — Challenge / stretch goals
Pick one or more:
- Convert the `mysql` Deployment to a **StatefulSet** with a
  `volumeClaimTemplate` — what actually changes, and why does it matter
  for a database specifically?
- Add a **HorizontalPodAutoscaler** for `employee-app` based on CPU.
- Add an **Ingress** resource so the app is reachable by hostname
  instead of NodePort.
- Introduce a **NetworkPolicy** so only `employee-app` pods can reach
  `mysql` and `redis` (deny-all baseline, then allow specific traffic).
- Package everything as a **Helm chart** with `values.yaml` overrides
  for replica counts, image tag, and resource limits.
- Set up a **CronJob** that runs `mysqldump` against the MySQL pod and
  stores the backup on a separate PVC.

---

## Troubleshooting tips

- Pod stuck in `Init:0/2` → check `kubectl logs <pod> -c wait-for-mysql`;
  usually means the MySQL/Redis Service name or port is wrong, or the
  target Deployment isn't Ready yet.
- `CrashLoopBackOff` on `employee-app` → check
  `kubectl logs <pod>`; almost always a wrong env var name/value from
  the ConfigMap/Secret.
- `Pending` PVC → check `kubectl get storageclass`; your cluster may
  need a default StorageClass (minikube has one built in).
- Can't reach the NodePort → confirm the Service's `selector` matches
  the pod's `labels` exactly, and that you're using the node's actual
  IP (`kubectl get nodes -o wide` for minikube, or `minikube ip`).
