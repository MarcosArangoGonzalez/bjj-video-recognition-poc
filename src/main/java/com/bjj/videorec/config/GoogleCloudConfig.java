package com.bjj.videorec.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "google.cloud")
@Data
public class GoogleCloudConfig {
    private String projectId;
    private Credentials credentials;
    private Storage storage;

    @Data
    public static class Credentials {
        private String location;
    }

    @Data
    public static class Storage {
        private String bucketName;
    }
}
