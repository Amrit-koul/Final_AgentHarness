"""Application-neutral validation of agent contracts."""
from .exceptions import ContractValidationError


class ContractValidator:
    REQUIRED = ("agent_id", "name", "owner", "business_function", "agent_type", "execution_mode", "adapter_type", "input_schema", "output_schema", "state_schema", "memory_schema")
    ADAPTERS = {"python_function", "langgraph", "rest_api", "external_webhook"}

    def validate(self, contract):
        errors = [f"Missing required field: {field}" for field in self.REQUIRED if not getattr(contract, field, None)]
        if contract.adapter_type not in self.ADAPTERS: errors.append(f"Unsupported adapter_type: {contract.adapter_type}")
        if contract.adapter_type in {"python_function", "langgraph"} and not contract.entrypoint: errors.append("Internal adapters require entrypoint")
        if contract.adapter_type in {"rest_api", "external_webhook"} and not contract.endpoint: errors.append("External adapters require endpoint")
        return errors

    def validate_or_raise(self, contract):
        errors = self.validate(contract)
        if errors: raise ContractValidationError(f"Invalid contract '{contract.agent_id}': " + "; ".join(errors))
