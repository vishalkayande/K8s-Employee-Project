# Kubernetes Live Project — Employee Directory

A hands-on Kubernetes project where I containerize a Python Flask application and deploy it on **Minikube** with MySQL and Redis.

This project is built to practice real Kubernetes concepts rather than just deploying a single container. The application uses:

* **Python Flask + Gunicorn** for the web application
* **MySQL** as the permanent database
* **Redis** as a cache and page-view counter
* **PersistentVolumeClaim (PVC)** for MySQL data persistence
* **ConfigMap** for non-sensitive configuration
* **Secret** for database credentials
* **Services** for communication between components
* **Init containers** to wait for dependencies
* **Liveness and readiness probes** for application health
* **NodePort** to expose the application outside the cluster

---

## 1. Project Architecture

The final Kubernetes setup looks like this:

```text
                         Browser
                            │
                            ▼
                ┌───────────────────────┐
                │ Service: employee-app │
                │      NodePort 30080   │
                └───────────┬───────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ Deployment: employee-app   │
              │                             │
              │ Flask + Gunicorn            │
              │ 2 replicas                  │
              └──────────┬──────────┬───────┘
                         │          │
              ┌──────────▼───┐  ┌───▼──────────┐
              │ Service      │  │ Service      │
              │ mysql        │  │ redis        │
              └──────┬───────┘  └──────┬───────┘
                     │                 │
              ┌──────▼────────┐  ┌─────▼────────┐
              │ MySQL         │  │ Redis        │
              │ 1 replica     │  │ 1 replica    │
              │               │  │              │
              │ PVC storage   │  │ In-memory    │
              └───────────────┘  └──────────────┘
```

### How the application works

When I open the application:

1. The browser sends a request to the `employee-app` NodePort Service.
2. Kubernetes sends the request to one of the Flask application pods.
3. Flask reads employee data from MySQL.
4. The application stores the employee list in Redis for 30 seconds.
5. Subsequent requests can be served from Redis.
6. MySQL remains the **source of truth**.
7. If Redis disappears, the application can fall back to MySQL.
8. If a MySQL pod is deleted, Kubernetes recreates it and the PVC keeps the database data.

This gives me a practical demonstration of how multiple Kubernetes workloads can work together.

---

# 2. Repository Structure

My project is organized like this:

```text
employee-directory/
│
├── app/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── templates/
│   └── static/
│
└── k8s/
    ├── 00-namespace.yaml
    ├── 01-secrets.yaml
    ├── 02-configmap.yaml
    ├── 03-mysql-pvc.yaml
    ├── 04-mysql-deployment.yaml
    ├── 05-mysql-service.yaml
    ├── 06-redis-deployment.yaml
    ├── 07-redis-service.yaml
    ├── 08-app-deployment.yaml
    └── 09-app-service.yaml
```

The Kubernetes manifests are numbered so that I can apply them in dependency order.

---

# 3. Prerequisites

Before starting, I need the following installed:

* Docker
* Minikube
* kubectl

I also need a working Minikube cluster.

Check the installations:

```bash
docker --version
minikube version
kubectl version --client
```

Start Minikube:

```bash
minikube start
```

Verify the cluster:

```bash
kubectl get nodes
```

I should see a node similar to:

```text
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   ...   ...
```

---

# 4. Start the Project

Clone the repository or move into my project directory:

```bash
cd employee-directory
```

Check the project files:

```bash
ls
```

I should see:

```text
app
k8s
README.md
```

---

# 5. Build the Docker Image

First, I build the Flask application image.

Move into the application directory:

```bash
cd app
```

Build the image:

```bash
docker build -t employee-app:1.0.0 .
```

Verify the image:

```bash
docker images | grep employee-app
```

Expected result:

```text
employee-app   1.0.0   ...
```

---

# 6. Load the Image into Minikube

Because I am using Minikube, I don't need to push this image to Docker Hub.

I can load the local image directly into Minikube:

```bash
minikube image load employee-app:1.0.0
```

Verify that Minikube can see the image:

```bash
minikube image ls | grep employee-app
```

> **Important:** The image name in `08-app-deployment.yaml` must match the image I built:
>
> ```yaml
> image: employee-app:1.0.0
> ```

---

# 7. Understand the Secret

Before deploying anything, I review:

```text
k8s/01-secrets.yaml
```

A Kubernetes Secret stores sensitive configuration such as:

* MySQL username
* MySQL password
* Database credentials

For example, a Secret might contain a value such as:

```text
YXBwdXNlcg==
```

This is only Base64 encoding.

I can decode it with:

```bash
echo 'YXBwdXNlcg==' | base64 -d
```

The result is:

```text
appuser
```

## Is Kubernetes Secret encryption?

Not automatically.

A Kubernetes Secret is **not automatically secure simply because the resource type is `Secret`**.

Base64 is encoding, not encryption.

Security also depends on:

* Kubernetes RBAC permissions
* Who can read Secrets
* Access to the Kubernetes API
* etcd security
* Encryption at rest
* Proper cluster configuration
* Protecting kubeconfig credentials

In a production cluster, I should consider enabling **encryption at rest for etcd** and applying restrictive RBAC policies.

---

# 8. Review the ConfigMap

Next, I check:

```text
k8s/02-configmap.yaml
```

The ConfigMap contains non-sensitive application configuration.

Typical values include:

```text
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=employees
REDIS_HOST=redis
REDIS_PORT=6379
```

The important Kubernetes concept here is:

```text
Secret     → sensitive values
ConfigMap  → non-sensitive configuration
```

---

# 9. Create the Kubernetes Namespace

I use a separate namespace for the project.

Apply the namespace:

```bash
kubectl apply -f k8s/00-namespace.yaml
```

Verify it:

```bash
kubectl get namespaces
```

I should see:

```text
emp-directory
```

From this point onward, most resources will be created inside:

```text
emp-directory
```

---

# 10. Apply the Secret

Apply the Secret:

```bash
kubectl apply -f k8s/01-secrets.yaml
```

Verify:

```bash
kubectl get secrets -n emp-directory
```

I should see the application/database Secret.

I can inspect the Secret metadata with:

```bash
kubectl describe secret -n emp-directory <secret-name>
```

I avoid exposing the actual secret values unnecessarily.

---

# 11. Apply the ConfigMap

Apply the ConfigMap:

```bash
kubectl apply -f k8s/02-configmap.yaml
```

Verify:

```bash
kubectl get configmaps -n emp-directory
```

I can inspect it with:

```bash
kubectl describe configmap -n emp-directory <configmap-name>
```

---

# 12. Create MySQL Persistent Storage

MySQL needs persistent storage because the database should survive pod deletion.

Apply the PVC:

```bash
kubectl apply -f k8s/03-mysql-pvc.yaml
```

Check the PVC:

```bash
kubectl get pvc -n emp-directory
```

Expected status:

```text
STATUS
Bound
```

I can also check the StorageClass:

```bash
kubectl get storageclass
```

On Minikube, a default StorageClass is normally available.

If the PVC remains `Pending`, I check:

```bash
kubectl describe pvc -n emp-directory <pvc-name>
```

---

# 13. Deploy MySQL

Now I deploy MySQL:

```bash
kubectl apply -f k8s/04-mysql-deployment.yaml
```

Check the deployment:

```bash
kubectl get deployments -n emp-directory
```

Check the pods:

```bash
kubectl get pods -n emp-directory
```

Watch the MySQL pod:

```bash
kubectl get pods -n emp-directory -w
```

I wait until MySQL shows:

```text
1/1 Running
```

and is Ready.

I can inspect the pod:

```bash
kubectl describe pod -n emp-directory -l app=mysql
```

If MySQL does not start, check its logs:

```bash
kubectl logs -n emp-directory -l app=mysql
```

---

# 14. Create the MySQL Service

The application should not connect directly to the MySQL pod IP.

Instead, Kubernetes provides a stable DNS name through a Service.

Apply:

```bash
kubectl apply -f k8s/05-mysql-service.yaml
```

Check it:

```bash
kubectl get service -n emp-directory
```

The application can now use:

```text
mysql
```

as the MySQL hostname.

Inside the Kubernetes namespace, Kubernetes DNS resolves:

```text
mysql
```

to the MySQL Service.

---

# 15. Deploy Redis

Now I deploy Redis:

```bash
kubectl apply -f k8s/06-redis-deployment.yaml
```

Check:

```bash
kubectl get pods -n emp-directory
```

Wait until Redis is Ready.

Then create the Redis Service:

```bash
kubectl apply -f k8s/07-redis-service.yaml
```

Check:

```bash
kubectl get services -n emp-directory
```

I should now have both:

```text
mysql
redis
```

---

# 16. Test Redis

I can verify that Redis is responding using:

```bash
kubectl exec -n emp-directory deploy/redis -- redis-cli ping
```

Expected output:

```text
PONG
```

This confirms that the Redis container is running and responding to commands.

---

# 17. Deploy the Flask Application

At this point I have:

```text
Namespace
   │
   ├── Secret
   ├── ConfigMap
   ├── MySQL PVC
   ├── MySQL Deployment
   ├── MySQL Service
   ├── Redis Deployment
   └── Redis Service
```

Now I deploy the application.

Apply:

```bash
kubectl apply -f k8s/08-app-deployment.yaml
```

Check the deployment:

```bash
kubectl get deployments -n emp-directory
```

Check the pods:

```bash
kubectl get pods -n emp-directory
```

The application should eventually have two replicas:

```text
employee-app-xxxxx   1/1   Running
employee-app-yyyyy   1/1   Running
```

---

# 18. Understand the Init Containers

The application deployment uses init containers to make sure required dependencies are available before Flask starts.

Check the application pods:

```bash
kubectl get pods -n emp-directory
```

If a pod is showing:

```text
Init:0/2
```

the init containers are still running.

I can check the first init container:

```bash
kubectl logs -n emp-directory <app-pod-name> -c wait-for-mysql
```

If there is another init container, I can inspect it with:

```bash
kubectl logs -n emp-directory <app-pod-name> -c <container-name>
```

The purpose is to prevent the Flask application from starting before its dependencies are available.

---

# 19. Check the Application Logs

Once the application pod is running:

```bash
kubectl logs -n emp-directory <app-pod-name>
```

For continuous logs:

```bash
kubectl logs -f -n emp-directory <app-pod-name>
```

I should see Gunicorn starting and listening on the configured application port.

---

# 20. Create the Application Service

Expose the application using the NodePort Service:

```bash
kubectl apply -f k8s/09-app-service.yaml
```

Check:

```bash
kubectl get service -n emp-directory
```

The application Service should expose:

```text
NodePort: 30080
```

---

# 21. Access the Application

Because I am using Minikube, the easiest way to access the application is:

```bash
minikube service employee-app -n emp-directory --url
```

This returns a URL.

Open that URL in my browser.

Alternatively, I can get the Minikube IP:

```bash
minikube ip
```

Then access:

```text
http://<minikube-ip>:30080
```

---

# 22. Verify the Complete Deployment

At this point, I check everything together:

```bash
kubectl get all -n emp-directory
```

I should have:

* 2 employee-app pods
* 1 MySQL pod
* 1 Redis pod
* employee-app Service
* MySQL Service
* Redis Service
* Deployments for all three applications

Check persistent storage:

```bash
kubectl get pvc -n emp-directory
```

The MySQL PVC should be:

```text
Bound
```

---

# 23. Test the Employee Directory

Open the application in the browser.

Add a few employees.

For example:

```text
Name: John
Department: IT
Email: john@example.com
```

Add another employee as well.

Refresh the page and verify that the employees are displayed.

---

# 24. Verify Redis Caching

The application uses Redis as a cache.

The page should indicate the source of the data, such as:

```text
MySQL (fresh)
```

or:

```text
Redis Cache
```

Refresh the page rapidly several times.

The goal is to observe the application switching between:

```text
MySQL → Redis Cache
```

This proves that Redis is actually being used as a cache rather than simply existing as an unused Kubernetes pod.

---

# 25. Verify MySQL Persistence

Now I intentionally delete the MySQL pod:

```bash
kubectl delete pod -n emp-directory -l app=mysql
```

Because MySQL is managed by a Deployment, Kubernetes creates a replacement pod.

Watch it:

```bash
kubectl get pods -n emp-directory -w
```

Wait until the new MySQL pod is:

```text
1/1 Running
```

Then refresh the Employee Directory.

The employees I created earlier should still exist.

### Why did the data survive?

The MySQL pod itself is disposable.

The data is stored on the PVC:

```text
MySQL Pod
    │
    ▼
PersistentVolumeClaim
    │
    ▼
Persistent Storage
```

Therefore:

```text
Pod deleted ≠ Database data deleted
```

This is one of the most important concepts in this project.

---

# 26. Verify Redis Is Only a Cache

Now delete the Redis pod:

```bash
kubectl delete pod -n emp-directory -l app=redis
```

Kubernetes recreates it automatically.

Check:

```bash
kubectl get pods -n emp-directory
```

While Redis is unavailable, the application should still be able to retrieve employee data from MySQL.

This demonstrates the architecture:

```text
MySQL
  │
  └── Source of Truth

Redis
  │
  └── Cache
```

If Redis disappears, employee records should not disappear.

---

# 27. Test the Readiness Probe

Now I intentionally break the MySQL dependency.

Scale MySQL down to zero:

```bash
kubectl scale deployment/mysql -n emp-directory --replicas=0
```

Verify:

```bash
kubectl get pods -n emp-directory
```

The MySQL pod should disappear.

Now check the application readiness endpoint.

First, identify an application pod:

```bash
kubectl get pods -n emp-directory
```

Port-forward it:

```bash
kubectl port-forward -n emp-directory pod/<app-pod-name> 8080:<app-port>
```

Then open:

```text
http://localhost:8080/ready
```

The readiness endpoint should report that MySQL is unavailable.

The HTTP response should be:

```text
503 Service Unavailable
```

This demonstrates that readiness is not just a fake endpoint. It actually checks backend dependencies.

---

# 28. Recover MySQL

Scale MySQL back to one replica:

```bash
kubectl scale deployment/mysql -n emp-directory --replicas=1
```

Watch the pod:

```bash
kubectl get pods -n emp-directory -w
```

Wait until MySQL becomes Ready.

Then check the application again.

The `/ready` endpoint should return successfully once the database connection is restored.

---

# 29. Useful Kubernetes Commands

These are the commands I use most often while working on this project.

### View all resources

```bash
kubectl get all -n emp-directory
```

### View pods

```bash
kubectl get pods -n emp-directory
```

### Watch pods

```bash
kubectl get pods -n emp-directory -w
```

### View deployments

```bash
kubectl get deployments -n emp-directory
```

### View Services

```bash
kubectl get services -n emp-directory
```

### View PVC

```bash
kubectl get pvc -n emp-directory
```

### View ConfigMaps

```bash
kubectl get configmaps -n emp-directory
```

### View Secrets

```bash
kubectl get secrets -n emp-directory
```

### Describe a pod

```bash
kubectl describe pod -n emp-directory <pod-name>
```

### View application logs

```bash
kubectl logs -n emp-directory <pod-name>
```

### Follow application logs

```bash
kubectl logs -f -n emp-directory <pod-name>
```

### Execute a command inside a pod

```bash
kubectl exec -it -n emp-directory <pod-name> -- /bin/sh
```

### Check events

```bash
kubectl get events -n emp-directory --sort-by=.lastTimestamp
```

---

# 30. Troubleshooting

## Pod stuck at `Init:0/2`

Check the init container:

```bash
kubectl logs -n emp-directory <pod-name> -c wait-for-mysql
```

Also check:

```bash
kubectl get pods -n emp-directory
kubectl get services -n emp-directory
```

Common causes:

* MySQL is not Ready
* Redis is not Ready
* Wrong Service name
* Wrong port
* Incorrect DNS name
* Backend Deployment has failed

---

## Application in `CrashLoopBackOff`

Check the application logs:

```bash
kubectl logs -n emp-directory <pod-name>
```

Also inspect the pod:

```bash
kubectl describe pod -n emp-directory <pod-name>
```

Check the ConfigMap and Secret values used by the application.

Typical causes:

* Incorrect environment variable
* Wrong database hostname
* Wrong database credentials
* Wrong Redis hostname
* Application startup error

---

## PVC stuck in `Pending`

Check:

```bash
kubectl get pvc -n emp-directory
```

Then:

```bash
kubectl describe pvc -n emp-directory <pvc-name>
```

Check available StorageClasses:

```bash
kubectl get storageclass
```

For Minikube, I should normally have a default StorageClass.

---

## Cannot access the application

Check the Service:

```bash
kubectl get service employee-app -n emp-directory
```

Check the pods:

```bash
kubectl get pods -n emp-directory
```

Check Service endpoints:

```bash
kubectl get endpoints -n emp-directory
```

Make sure the Service selector matches the labels on the application pods.

For Minikube, the easiest option is:

```bash
minikube service employee-app -n emp-directory --url
```

---

# 31. Clean Up the Project

When I am finished experimenting, I can remove the entire project namespace:

```bash
kubectl delete namespace emp-directory
```

Check:

```bash
kubectl get namespaces
```

The `emp-directory` namespace should eventually disappear.

> **Warning:** Deleting the namespace removes the Kubernetes resources inside it, including the PVC. Depending on the storage provisioner and reclaim policy, persistent data may also be deleted.

---

# 32. Stretch Goals

Once the basic deployment works, I can extend the project.

## 32.1 Convert MySQL Deployment to StatefulSet

Convert:

```text
Deployment → StatefulSet
```

and use:

```yaml
volumeClaimTemplates:
```

The goal is to understand why databases often benefit from StatefulSets.

Important concepts to explore:

* Stable pod identity
* Stable network identity
* Persistent storage per replica
* Ordered startup/shutdown
* Stateful workloads vs stateless workloads

---

## 32.2 Add a HorizontalPodAutoscaler

Add an HPA for:

```text
employee-app
```

Scale based on CPU utilization.

This lets Kubernetes automatically increase or decrease application replicas based on load.

---

## 32.3 Add an Ingress

Instead of exposing the application through:

```text
NodePort 30080
```

I can introduce an Ingress and access the application through a hostname such as:

```text
employee.local
```

This gives me experience with:

```text
Browser
   ↓
Ingress
   ↓
Service
   ↓
Pods
```

---

## 32.4 Add NetworkPolicies

Create a default-deny policy and then explicitly allow:

```text
employee-app → mysql
employee-app → redis
```

The goal is to prevent unrelated pods from communicating with the database and cache.

---

## 32.5 Create a Helm Chart

Package the project as a Helm chart.

Possible configurable values:

```yaml
replicaCount: 2

image:
  repository: employee-app
  tag: "1.0.0"

resources:
  requests:
    cpu: ...
    memory: ...
```

This would make the deployment easier to customize and reuse.

---

## 32.6 Add MySQL Backups

Create a Kubernetes CronJob that periodically runs:

```text
mysqldump
```

and stores the backup separately.

This would turn the project into a more realistic database deployment exercise.

---

# 33. What I Learned From This Project

This project gives me hands-on experience with several important Kubernetes concepts:

| Kubernetes Concept | Where I Used It                  |
| ------------------ | -------------------------------- |
| Namespace          | `emp-directory`                  |
| Secret             | MySQL/application credentials    |
| ConfigMap          | Application configuration        |
| Deployment         | Flask, MySQL, Redis              |
| Service            | Application, MySQL, Redis        |
| NodePort           | External application access      |
| PVC                | Persistent MySQL storage         |
| Init Container     | Dependency checks                |
| Liveness Probe     | Application health               |
| Readiness Probe    | Backend availability             |
| Kubernetes DNS     | Service-to-service communication |
| Scaling            | MySQL failure/recovery test      |
| Pod replacement    | MySQL persistence test           |
| Caching            | Redis                            |
| Persistent storage | MySQL PVC                        |

The main architecture I want to remember is:

```text
                 Kubernetes Cluster
                        │
          ┌─────────────┴─────────────┐
          │                           │
     employee-app                  Backend
       2 replicas                     │
          │                    ┌───────┴───────┐
          │                    │               │
          ▼                    ▼               ▼
       Service              MySQL            Redis
          │                    │               │
       NodePort                ▼               │
          │                   PVC              │
          ▼                                    │
       Browser                         Cache + Counter
```

---

# 34. Final Verification Checklist

Before considering the project complete, I verify the following:

```text
[ ] Minikube cluster is running
[ ] Docker image built successfully
[ ] Image loaded into Minikube
[ ] Namespace created
[ ] Secret created
[ ] ConfigMap created
[ ] MySQL PVC is Bound
[ ] MySQL pod is Running and Ready
[ ] MySQL Service is available
[ ] Redis pod is Running and Ready
[ ] Redis Service is available
[ ] Redis responds with PONG
[ ] Employee app has 2 Ready replicas
[ ] Init containers completed successfully
[ ] Application Service is available
[ ] Application opens through Minikube
[ ] Employees can be added
[ ] Redis caching can be observed
[ ] MySQL data survives pod deletion
[ ] Application survives Redis pod deletion
[ ] /ready returns 503 when MySQL is unavailable
[ ] /ready recovers after MySQL is restored
```

---

# 35. Final Result

At the end of this project, I have a complete Kubernetes-based Employee Directory running on Minikube:

```text
                    Browser
                       │
                       ▼
              ┌─────────────────┐
              │ employee-app    │
              │ NodePort :30080 │
              └────────┬────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ Flask + Gunicorn    │
             │ 2 Kubernetes Pods   │
             └───────┬───────┬─────┘
                     │       │
              ┌──────▼───┐ ┌─▼────────┐
              │  MySQL   │ │  Redis   │
              │  + PVC   │ │  Cache   │
              └──────────┘ └──────────┘
```

The important part is not just getting the application running.

I am using this project to understand **how Kubernetes manages application lifecycle, service discovery, persistent storage, configuration, secrets, caching, health checks, and failure recovery** in a realistic multi-container application.
