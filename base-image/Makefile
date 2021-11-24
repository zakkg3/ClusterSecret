IMG_NAMESPACE = flag5
IMG_NAME = clustersecretbase
IMG_FQNAME = $(IMG_NAMESPACE)/$(IMG_NAME)
IMG_VERSION = 0.0.4

.PHONY: container arm-container push clean clean-arm
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
	
arm-push:
	sudo docker push $(IMG_FQNAME):$(IMG_VERSION)_arm32

clean-arm:
	sudo docker rmi $(IMG_FQNAME):$(IMG_VERSION)_arm32
