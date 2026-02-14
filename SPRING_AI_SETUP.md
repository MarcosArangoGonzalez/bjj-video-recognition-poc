# Spring AI Configuration Guide

## Overview

This project uses **Spring AI** to provide a flexible, provider-agnostic interface for AI model integration. You can easily switch between different AI providers (Google Gemini, OpenAI, Anthropic, etc.) by simply changing the configuration in `application.yml`.

## Current Configuration

### Active Provider: Google Vertex AI Gemini

The application is currently configured to use **Gemini 1.5 Flash** via Google Cloud's Vertex AI.

## Prerequisites

### For Google Vertex AI Gemini (Current Setup)

1. **Google Cloud Project**: Create a project at [Google Cloud Console](https://console.cloud.google.com/)
2. **Enable Vertex AI API**: Enable the Vertex AI API for your project
3. **Service Account**: Create a service account with Vertex AI permissions
4. **Credentials**: Download the JSON credentials file

### For OpenAI (Alternative)

1. **OpenAI Account**: Sign up at [OpenAI Platform](https://platform.openai.com/)
2. **API Key**: Generate an API key from your account dashboard

## Environment Variables

### Google Vertex AI (Current)

```bash
export GOOGLE_CLOUD_PROJECT_ID=your-google-cloud-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json
```

### OpenAI (Alternative)

```bash
export OPENAI_API_KEY=sk-...your-api-key
```

## Switching AI Providers

### Option 1: Use Google Vertex AI Gemini (Default)

In `application.yml`, ensure this section is **uncommented**:

```yaml
spring:
  ai:
    vertex:
      ai:
        gemini:
          project-id: ${GOOGLE_CLOUD_PROJECT_ID:your-project-id}
          location: ${GOOGLE_CLOUD_LOCATION:us-central1}
          chat:
            options:
              model: gemini-1.5-flash-002
              temperature: 0.1
              max-output-tokens: 2048
```

### Option 2: Use OpenAI

In `application.yml`:

1. **Comment out** the Vertex AI section
2. **Uncomment** the OpenAI section:

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY:your-api-key}
      chat:
        options:
          model: gpt-4o-mini
          temperature: 0.1
          max-tokens: 2048
```

## Available Models

### Google Gemini Models

- `gemini-1.5-flash-002` - Fast, cost-effective (current)
- `gemini-1.5-pro-002` - More capable, higher cost
- `gemini-2.0-flash-exp` - Latest experimental

### OpenAI Models

- `gpt-4o-mini` - Fast and affordable
- `gpt-4o` - Most capable
- `gpt-4-turbo` - Balance of speed and capability

## Configuration Parameters

### Common Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `temperature` | Creativity vs consistency | 0.0 - 2.0 | 0.4 |
| `max-tokens` / `max-output-tokens` | Maximum response length | 1 - 8192+ | 2048 |

### Temperature Guidelines

- **0.0 - 0.3**: Highly deterministic, best for structured tasks
- **0.4 - 0.7**: Balanced creativity and consistency ✅ (Current)
- **0.8 - 1.0**: More creative and varied
- **1.0+**: Highly creative, less predictable

## Testing the Configuration

1. **Build the project**:
   ```bash
   mvn clean install
   ```

2. **Run the application**:
   ```bash
   mvn spring-boot:run
   ```

3. **Check logs**: Look for Spring AI initialization messages

## Troubleshooting

### Google Vertex AI Issues

**Error**: `Permission denied` or `403 Forbidden`
- **Solution**: Ensure your service account has the `Vertex AI User` role
- **Verify**: Run `gcloud auth application-default login`

**Error**: `API not enabled`
- **Solution**: Enable Vertex AI API in Google Cloud Console

### OpenAI Issues

**Error**: `Invalid API Key`
- **Solution**: Verify your API key is correct and active
- **Check**: Visit OpenAI Platform to validate your key

**Error**: `Rate limit exceeded`
- **Solution**: Check your OpenAI usage limits and upgrade if needed

## Cost Considerations

### Google Gemini Pricing (as of 2024)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Gemini 1.5 Flash | $0.075 | $0.30 |
| Gemini 1.5 Pro | $1.25 | $5.00 |

### OpenAI Pricing (as of 2024)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| GPT-4o-mini | $0.15 | $0.60 |
| GPT-4o | $2.50 | $10.00 |

## Code Implementation

The implementation is provider-agnostic thanks to Spring AI:

```java
@Service
public class SpringAiAnalysisService implements AiAnalysisService {
    
    private final ChatClient chatClient;
    
    public SpringAiAnalysisService(ChatClient.Builder chatClientBuilder) {
        // Spring AI automatically injects the correct provider
        this.chatClient = chatClientBuilder.build();
    }
    
    @Override
    public List<GeminiDetection> analyzeFrame(File frameFile, double timestamp) {
        // Works with any configured provider!
        GeminiResponse response = chatClient.prompt()
            .user(u -> u
                .text(prompt)
                .media(MimeTypeUtils.IMAGE_JPEG, new FileSystemResource(frameFile)))
            .call()
            .entity(GeminiResponse.class);
        
        return response.getDetections();
    }
}
```

## Next Steps

1. Set up your chosen provider's credentials
2. Configure environment variables
3. Test the integration
4. Monitor usage and costs
5. Adjust temperature and model as needed

## References

- [Spring AI Documentation](https://docs.spring.io/spring-ai/reference/)
- [Google Vertex AI Gemini](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
