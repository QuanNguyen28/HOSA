const MESSAGES: Record<string, string> = {
  OPENAI_UNAVAILABLE: "The LLM proxy is temporarily unavailable. Please try sending your message again.",
  OPENAI_CONNECT_TIMEOUT: "Could not establish a connection to the LLM proxy. Please try again.",
  OPENAI_RATE_LIMIT: "The LLM proxy is limiting requests. Please wait and try again.",
  OPENAI_AUTH_FAILED: "The LLM proxy rejected its access key. Check the configured proxy credentials.",
  OPENAI_NOT_CONFIGURED: "The LLM proxy has not been configured on the server.",
  OPENAI_INVALID_BASE_URL: "The LLM proxy address is invalid. Check the server configuration.",
  OPENAI_MODEL_NOT_FOUND: "The configured model is not available through the LLM proxy.",
  OPENAI_INVALID_REQUEST: "The LLM proxy could not accept this request. Check the technical details.",
};

export function assistantErrorMessage(code: string): string {
  return MESSAGES[code] ?? code;
}
