# Kubernetes Employee Directory

A containerized Employee Directory application deployed on Kubernetes using Python Flask, MySQL, Redis, and persistent storage.

The project demonstrates a practical multi-tier Kubernetes architecture using Deployments, Services, ConfigMaps, Secrets, PersistentVolumeClaims, Init Containers, and application health probes.

---

## Architecture

```
                              Browser
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  employee-app Service  │
                    │      NodePort :30080   │
                    └────────────┬───────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │    employee-app Deployment   │
                 │                              │
                 │      Flask + Gunicorn        │
                 │         2 Replicas           │
                 └─────────────┬───────┬────────┘
                               │       │
                    ┌──────────▼───┐ ┌─▼────────────┐
                    │ MySQL Service│ │ Redis Service│
                    └───────┬──────┘ └──────┬───────┘
                            │               │
                    ┌───────▼──────┐ ┌─────▼──────┐
                    │    MySQL     │ │    Redis   │
                    │   1 Replica  │ │   1 Replica│
                    │              │ │            │
                    │ Employee DB  │ │ Cache +    │
                    │              │ │ Counter    │
                    └───────┬──────┘ └────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │       PVC       │
                    │ Persistent Data │
                    └─────────────────┘
```

### Application Flow

```
User
 │
 ▼
employee-app Service
 │
 ▼
Flask Application
 │
 ├──────────────► MySQL
 │                  │
 │                  └── Persistent Storage
 │
 └──────────────► Redis
                    ├── Employee Cache
                    └── Page-View Counter
```

- **MySQL** is the source of truth.
- **Redis** is used for caching and page-view counting.

---

## Key Features

- Python Flask application with Gunicorn
- Docker containerization
- Kubernetes Deployments
- MySQL database
- Redis caching
- Redis page-view counter
- PersistentVolumeClaim (PVC) for MySQL storage
- ConfigMap for application configuration
- Secret for database credentials
- Kubernetes Services for internal communication
- Init Containers for dependency checks
- Liveness and Readiness Probes
- NodePort for application access
- Multiple Flask application replicas
- Persistent database data across pod recreation
- Redis fallback to MySQL when the cache is unavailable

---

## Technology Stack

| Component             | Technology            |
|-----------------------|-----------------------|
| Application           | Python / Flask        |
| Application Server    | Gunicorn              |
| Containerization      | Docker                |
| Orchestration         | Kubernetes            |
| Database              | MySQL                 |
| Cache                 | Redis                 |
| Storage               | PersistentVolumeClaim |
| Configuration         | ConfigMap             |
| Credentials           | Kubernetes Secret     |
| Cluster Environment   | Killercoda Kubernetes |

---

## Project Structure

```
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

The Kubernetes manifests are numbered to represent the deployment order and dependencies between resources.

---

## Deployment

### Prerequisites

The project requires:

- Docker
- kubectl
- A working Kubernetes cluster
- A container registry accessible by the Kubernetes cluster


### 1. Build the Application Image

Move into the application directory:

```bash
cd app
```

Build the Docker image:

```bash
docker build -t <dockerhub-username>/employee-app:1.0.0 .
```

Push the image to a container registry:

```bash
docker push <dockerhub-username>/employee-app:1.0.0
```

Update the image reference in `k8s/08-app-deployment.yaml` with:

```yaml
image: <dockerhub-username>/employee-app:1.0.0
```

Return to the project root:

```bash
cd ..
```

### 2. Create the Namespace

```bash
kubectl apply -f k8s/00-namespace.yaml
```

All application resources are deployed inside the `emp-directory` namespace.

### 3. Apply Configuration

Create the Kubernetes Secret:

```bash
kubectl apply -f k8s/01-secrets.yaml
```

Create the ConfigMap:

```bash
kubectl apply -f k8s/02-configmap.yaml
```

The Secret contains sensitive database credentials, while the ConfigMap contains non-sensitive application configuration.

### 4. Deploy MySQL

Create the persistent storage claim:

```bash
kubectl apply -f k8s/03-mysql-pvc.yaml
```

Deploy MySQL:

```bash
kubectl apply -f k8s/04-mysql-deployment.yaml
```

Create the MySQL Service:

```bash
kubectl apply -f k8s/05-mysql-service.yaml
```

The application communicates with MySQL through the Kubernetes Service rather than directly using the MySQL pod. The PVC provides persistent storage for the database.

### 5. Deploy Redis

```bash
kubectl apply -f k8s/06-redis-deployment.yaml
kubectl apply -f k8s/07-redis-service.yaml
```

Redis is used for:

- Employee-list caching
- Page-view counting

Redis is not the permanent source of employee data.

### 6. Deploy the Flask Application

```bash
kubectl apply -f k8s/08-app-deployment.yaml
```

The application Deployment creates two Flask/Gunicorn replicas. Init containers ensure the required backend dependencies are available before the application starts.

The application also provides:

- `/health` — for liveness checks
- `/ready` — for readiness checks

### 7. Expose the Application

```bash
kubectl apply -f k8s/09-app-service.yaml
```

The application is exposed through **NodePort: 30080**.

Access the application using:

```
http://<node-ip>:30080
```

### Complete Deployment

All Kubernetes manifests can also be applied together:

```bash
kubectl apply -f k8s/
```

Because the manifests are numbered, they are applied in the intended dependency order.

---

## Kubernetes Resources

| Resource               | Purpose                               |
|------------------------|---------------------------------------|
| Namespace              | Isolates project resources            |
| Deployment             | Manages Flask, MySQL, and Redis pods  |
| Service                | Provides stable networking            |
| ConfigMap              | Stores non-sensitive configuration    |
| Secret                 | Stores database credentials           |
| PersistentVolumeClaim  | Provides persistent MySQL storage     |
| Init Container         | Waits for required dependencies       |
| Liveness Probe         | Checks application health             |
| Readiness Probe        | Checks backend availability           |
| NodePort               | Exposes the application               |

---

## Data & Caching

The application follows a simple source-of-truth and caching model:

```
                    Employee Request
                           │
                           ▼
                    Flask Application
                           │
                    ┌──────┴──────┐
                    │             │
                 Redis          MySQL
                  Cache       Source of Truth
                    │             │
                    │             ▼
                    │       Persistent Storage
                    │
                    └── Cached for 30 seconds
```

- MySQL stores employee records permanently.
- Redis temporarily caches the employee list and maintains the page-view counter.
- If Redis becomes unavailable, the application can continue retrieving data from MySQL.

---

## Persistence

MySQL uses a Kubernetes PersistentVolumeClaim:

```
MySQL Pod
    │
    ▼
PersistentVolumeClaim
    │
    ▼
Persistent Storage
```

This means MySQL data is not tied to the lifetime of a particular pod. If the MySQL pod is recreated, the database can continue using the existing persistent storage.

---

## Health Checks

The Flask application provides two health endpoints.

### Liveness — `/health`

Used to determine whether the application process is alive.

### Readiness — `/ready`

Used to determine whether the application is ready to serve traffic and can communicate with its required backend services.

This allows Kubernetes to distinguish between **Running** and **Ready to receive traffic**.

---

## Kubernetes Concepts Demonstrated

**Containerization**
The Flask application is packaged into a Docker image and deployed as a Kubernetes workload.

**Deployments**
Deployments manage the employee application replicas, MySQL, and Redis.

**Services**
Services provide stable network identities for the employee application, MySQL, and Redis.

**ConfigMap**
Stores non-sensitive configuration separately from application code.

**Secret**
Stores database credentials separately from regular configuration.

**Persistent Storage**
A PVC provides persistent storage for MySQL.

**Init Containers**
Init containers ensure required dependencies are available before the application starts.

**Health Probes**
Liveness and readiness probes provide Kubernetes with application health information.

**Caching**
Redis reduces repeated database access by temporarily caching employee data.

---

## Application Behavior

```
                    ┌───────────────┐
                    │     MySQL     │
                    │  Source of    │
                    │     Truth     │
                    └───────┬───────┘
                            │
                            │ Employee Data
                            ▼
                    ┌───────────────┐
                    │   Flask App   │
                    └───────┬───────┘
                            │
                            │ Cache
                            ▼
                    ┌───────────────┐
                    │     Redis     │
                    │   30-sec      │
                    │     Cache     │
                    └───────────────┘
```

This demonstrates that Redis is an independent caching layer rather than a replacement for the database.

---

## Future Enhancements

Possible extensions for the project include:

- Convert MySQL Deployment to a StatefulSet
- Add a HorizontalPodAutoscaler
- Add an Ingress
- Implement NetworkPolicies
- Package the application as a Helm Chart
- Add automated MySQL backups using a CronJob

---

## Project Summary

Kubernetes Employee Directory demonstrates a complete multi-tier application deployed on Kubernetes. The project combines:

```
Docker
   │
   ▼
Flask + Gunicorn
   │
   ├──────────────┐
   ▼              ▼
MySQL           Redis
   │              │
   ▼              ├── Cache
PVC              └── Counter
   │
   ▼
Persistent Data
```
