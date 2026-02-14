# Guía Rápida: Cambiar de Modelo en Spring AI

## Configuración Actual

Tu aplicación está configurada para usar **Google Vertex AI Gemini 1.5 Flash**.

## Variables de Entorno Necesarias

### Para Vertex AI Gemini (actual):
```bash
export GOOGLE_CLOUD_PROJECT_ID=tu-proyecto-gcp
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/credenciales.json
```

## Cómo Cambiar de Modelo

### Opción 1: Cambiar el modelo de Gemini

En `application.yml`, línea 46, cambia:
```yaml
model: gemini-1.5-flash-002    # Rápido y económico
# O usa:
# model: gemini-1.5-pro-002     # Más potente
# model: gemini-2.0-flash-exp   # Experimental
```

### Opción 2: Cambiar a OpenAI

1. En `pom.xml`, **descomenta** (líneas 91-95):
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
</dependency>
```

2. En `application.yml`, **comenta** la sección Vertex AI (líneas 38-48) y **descomenta** OpenAI (líneas 50-57)

3. Define la variable de entorno:
```bash
export OPENAI_API_KEY=sk-tu-clave-aqui
```

## Modelos Disponibles

### Google Gemini
- `gemini-1.5-flash-002` ✅ (actual) - Mejor relación calidad/precio
- `gemini-1.5-pro-002` - Mayor capacidad
- `gemini-2.0-flash-exp` - Versión experimental

### OpenAI
- `gpt-4o-mini` - Rápido y económico
- `gpt-4o` - Más capaz
- `gpt-4-turbo` - Balance

## Probar la Configuración

```bash
# Compilar
mvn clean install

# Ejecutar
mvn spring-boot:run
```

**📝 Nota**: No necesitas cambiar código, solo configuración en `application.yml` y variables de entorno.

Ver [`SPRING_AI_SETUP.md`](./SPRING_AI_SETUP.md) para información detallada.
