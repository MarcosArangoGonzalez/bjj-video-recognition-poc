package com.bjj.videorec.config;

import org.springframework.context.annotation.Configuration;

/**
 * Spring AI Configuration
 * 
 * This configuration provides a ChatClient.Builder bean that can be used
 * to create ChatClient instances. The actual model provider (Gemini, OpenAI,
 * etc.)
 * is configured in application.yml and auto-configured by Spring AI.
 */
@Configuration
public class SpringAiConfig {

    // Spring AI autoconfigures a ChatClient.Builder bean automatically.
    // We don't need to define it here unless we want to customize it globally.
    // This class can be used in the future to add global ChatClient customizations
    // (default advisors, etc.)
}
