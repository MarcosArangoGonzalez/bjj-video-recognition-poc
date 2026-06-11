package com.bjj.videorec.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import java.util.ArrayList;
import java.util.List;

@Configuration
public class SpringAiConfig {

    @Value("${spring.ai.openai.api-key:}")
    private String key1;

    @Value("${GEMINI_API_KEY_2:}")
    private String key2;

    @Value("${GEMINI_API_KEY_3:}")
    private String key3;

    @Value("${spring.ai.openai.base-url:https://api.openai.com}")
    private String baseUrl;

    @Value("${spring.ai.openai.chat.options.model:gemini-2.0-flash}")
    private String model;

    @Bean
    @Primary
    public List<ChatClient> chatClients() {
        List<ChatClient> clients = new ArrayList<>();
        for (String key : List.of(key1, key2, key3)) {
            if (key != null && !key.isBlank()) {
                OpenAiApi api = new OpenAiApi(baseUrl, key);
                OpenAiChatModel chatModel = new OpenAiChatModel(api,
                        OpenAiChatOptions.builder().model(model).temperature(0.1).build());
                clients.add(ChatClient.create(chatModel));
            }
        }
        return clients;
    }
}
