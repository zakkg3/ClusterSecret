IMG_NAMESPACE = flag5
IMG_NAME = clustersecret
IMG_FQNAME = $(IMG_NAMESPACE)/$(IMG_NAME)
IMG_VERSION = 0.0.9

.PHONY: container push clean arm-container arm-push arm-clean
all: container push
arm: arm-container arm-push
clean: clean arm-clean


container:
	sudo docker build -t $(IMG_FQNAME):$(IMG_VERSION) -t $(IMG_FQNAME):latest .

push: container
	sudo docker push $(IMG_FQNAME):$(IMG_VERSION)
	sudo docker push $(IMG_FQNAME):latest

clean:
	sudo docker rmi $(IMG_FQNAME):$(IMG_VERSION)

arm-container:
	sudo docker build -t $(IMG_FQNAME):$(IMG_VERSION)_arm32 -f Dockerfile.arm .
	
arm-push: arm-container
	sudo docker push $(IMG_FQNAME):$(IMG_VERSION)_arm32

arm-clean:
	sudo docker rmi $(IMG_FQNAME):$(IMG_VERSION)_arm32

beta:
	sudo docker build -t $(IMG_FQNAME):$(IMG_VERSION)-beta .
	sudo docker push $(IMG_FQNAME):$(IMG_VERSION)-beta

install:
	helm install clustersecret ./charts/cluster-secret -n clustersecret --create-namespace

test-env:
	podman machine start
	KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster
	helm install clustersecret ./charts/cluster-secret -n clustersecret --create-namespace

stop-test-env:
	KIND_EXPERIMENTAL_PROVIDER=podman kind delete cluster
	podman machine stop

chart-update:
	helm package charts/clustersecret/ -d docs/
	helm repo index ./docs
