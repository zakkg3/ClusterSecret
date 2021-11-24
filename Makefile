IMG_NAMESPACE = flag5
IMG_NAME = clustersecret
IMG_FQNAME = $(IMG_NAMESPACE)/$(IMG_NAME)
IMG_VERSION = 0.0.6

.PHONY: container push clean
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
