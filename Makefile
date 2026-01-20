
GO_BUILD_ENV :=
GO_BUILD_FLAGS :=
MODULE_BINARY := bin/kettle-cycle-test

# Map Viam platform values to Go values
GOOS_VAL := $(VIAM_BUILD_OS)
GOARCH_VAL := $(VIAM_BUILD_ARCH)

# Map aarch64 -> arm64 for Go compatibility
ifeq ($(GOARCH_VAL), aarch64)
	GOARCH_VAL := arm64
endif

ifeq ($(VIAM_TARGET_OS), windows)
	GO_BUILD_ENV += GOOS=windows GOARCH=amd64
	GO_BUILD_FLAGS := -tags no_cgo
	MODULE_BINARY = bin/kettle-cycle-test.exe
endif

$(MODULE_BINARY): Makefile go.mod *.go cmd/module/*.go
	GOOS=$(GOOS_VAL) GOARCH=$(GOARCH_VAL) $(GO_BUILD_ENV) go build $(GO_BUILD_FLAGS) -o $(MODULE_BINARY) cmd/module/main.go

lint:
	gofmt -s -w .

update:
	go get go.viam.com/rdk@latest
	go mod tidy

test:
	go test ./...

module.tar.gz: meta.json $(MODULE_BINARY)
ifneq ($(VIAM_TARGET_OS), windows)
	strip $(MODULE_BINARY)
endif
	tar czf $@ meta.json $(MODULE_BINARY)

module: test module.tar.gz

all: test module.tar.gz

setup:
	go mod tidy

PART_ID ?= $(shell jq -r '.part_id' machine.json)

reload-module:
	rm -f module.tar.gz $(MODULE_BINARY)
	viam module reload-local --part-id $(PART_ID)
	@echo "Module reloaded."

test-cycle:
	viam machine part run --part $(PART_ID) \
		--method 'viam.service.generic.v1.GenericService.DoCommand' \
		--data '{"name": "cycle-tester", "command": {"command": "execute_cycle"}}'

trial-start:
	viam machine part run --part $(PART_ID) \
		--method 'viam.service.generic.v1.GenericService.DoCommand' \
		--data '{"name": "cycle-tester", "command": {"command": "start"}}'

trial-stop:
	viam machine part run --part $(PART_ID) \
		--method 'viam.service.generic.v1.GenericService.DoCommand' \
		--data '{"name": "cycle-tester", "command": {"command": "stop"}}'

trial-status:
	viam machine part run --part $(PART_ID) \
		--method 'viam.service.generic.v1.GenericService.DoCommand' \
		--data '{"name": "cycle-tester", "command": {"command": "status"}}'
