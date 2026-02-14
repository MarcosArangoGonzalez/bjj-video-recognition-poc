package com.bjj.videorec.controller;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TestAiController {

    private final ChatClient chatClient;

    public TestAiController(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }

    @GetMapping("/api/test/ai")
    public String test() {
        try {
            return chatClient
                    .prompt("Di solo la palabra 'OK' si recibes esto correctamente.")
                    .call()
                    .content();
        } catch (Exception e) {
            return "ERROR: " + e.getMessage();
        }
    }
}
