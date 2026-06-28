"""vendor_src — migrated voice pipeline from CollectionAgent-trust-layer.

This package adapts the standalone voice pipeline to use the
banking_agents.collections_domain.* agents/services already ported
into the harness, avoiding duplicate code.

Exposed:
  voice_pipeline — build_voice_prompt, generate_greeting, process_voice_turn,
                   groq_configured
"""
