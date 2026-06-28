"""Generic adapter factory."""
from .adapters import ExternalWebhookAgentAdapter, LangGraphAgentAdapter, PythonFunctionAgentAdapter, RestApiAgentAdapter

ADAPTER_TYPES = {"python_function": PythonFunctionAgentAdapter, "langgraph": LangGraphAgentAdapter, "rest_api": RestApiAgentAdapter, "external_webhook": ExternalWebhookAgentAdapter}

def build_adapter(contract, services=None): return ADAPTER_TYPES[contract.adapter_type](contract, services)
