			.PHONY: image-bootstrap image-rebuild image-verify image-smoketest image-shell

			image-bootstrap:
    			./scripts/bootstrap_brew_image.sh

			image-rebuild:
    			./scripts/rebuild_image_env.sh

			image-verify:
    			./scripts/verify_image_env.sh

			image-smoketest:
    			source .venv-image/bin/activate && ./scripts/smoketest_image.sh

			image-shell:
    			./scripts/image_shell.sh

.PHONY: validate
validate:
	./tools/validate.sh
