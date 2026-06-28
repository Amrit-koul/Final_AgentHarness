"""Framework exceptions independent of any application domain."""


class HarnessError(Exception): pass
class ContractValidationError(HarnessError): pass
class AgentNotFoundError(HarnessError, KeyError): pass
class AgentDisabledError(HarnessError): pass
class PolicyBlockedError(HarnessError, PermissionError): pass
class AdapterError(HarnessError): pass
class AdapterConfigurationError(AdapterError): pass
class AdapterInvocationError(AdapterError): pass
class AdapterTimeoutError(AdapterInvocationError): pass
class AdapterConnectionError(AdapterInvocationError): pass
class AdapterResponseError(AdapterInvocationError): pass
