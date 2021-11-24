IMG_NAMESPACE = flag5
IMG_NAME = clustersecretbase
IMG_FQNAME = $(IMG_NAMESPACE)/$(IMG_NAME)
IMG_VERSION = 0.0.4

.PHONY: container arm-container push clean
all: container push


container:
	sudo docker build -t $(IMG_FQNAME):$(IMG_VERSION) -t $(IMG_FQNAME):latest .
	
arm-container:
	sudo docker build -t $(IMG_FQNAME):$(IMG_VERSION)_arm32 -f Dockerfile.arm .

push: container
	sudo docker push $(IMG_FQNAME):$(IMG_VERSION)
	# Also update :latest
	sudo docker push $(IMG_FQNAME):latest

clean:
	sudo docker rmi $(IMG_FQNAME):$(IMG_VERSION)
