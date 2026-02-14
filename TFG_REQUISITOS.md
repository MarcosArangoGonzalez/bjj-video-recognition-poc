# Requisitos del TFG: Plataforma Social de BJJ con Análisis de Vídeo

## 1. Funcionalidades Principales

### Gestión de Usuarios
- **Registro y autenticación**: Login seguro (email/password, OAuth opcional).
- **Perfil de usuario**: Gestión de datos personales, foto de perfil, cinturón/graduación, academia.

### Interacción Social
- **Feed de publicaciones**: Muro principal con actividad de usuarios seguidos y recomendaciones.
- **Interacciones**: Dar like, comentar y guardar técnicas en listas personalizadas.
- **Red Social**: Seguir/dejar de seguir usuarios, visualizar perfiles públicos.

### Gestión de Técnicas
- **Subida de contenido**: Carga de archivos de vídeo locales o enlaces de YouTube.
- **Gestión de contenido**: Edición de metadatos (título, descripción) y eliminación de publicaciones.
- **Reproductor**: Reproducción integrada de vídeos.

### Clasificación y Búsqueda Avanzada
- **Etiquetado**: Sistema de tags para técnicas (ej. "Armbar", "Guardia Cerrada").
- **Búsqueda tradicional**: Por título, descripción y etiquetas.
- **Filtrado**: Por tipo de técnica, dificultad, o creador.
- **[NUEVO] Búsqueda con Chat IA**: 
    - Asistente conversacional que permite buscar técnicas dentro de la base de datos mediante lenguaje natural (ej. "¿Cómo escapar de la montada?").
    - El sistema recupera las técnicas más relevantes de la plataforma y ofrece una respuesta resumida con enlaces a los vídeos.

## 2. Funcionalidades Adicionales (IA y Procesamiento)

### Análisis Automático de Vídeo (Gemini 2.5)
- **Extracción de frames**: Uso de ffmpeg para obtener imágenes clave.
- **Análisis Multimodal**: Identificación de técnicas y posiciones mediante IA.
- **Generación automática**:
    - Etiquetas sugeridas.
    - Descripción técnica inicial.
    - *Objetivo*: Facilitar la publicación y mejorar la indexación.

### [NUEVO] Gamificación y Aprendizaje Diario
- **Técnica del Día**: Sección destacada en el dashboard.
    - **Selección del Profesor**: Técnica global seleccionada por administradores/profesores.
    - **Selección Personalizada**: Recomendación basada en el nivel e intereses del usuario.
- **Sistema de Recompensas**:
    - **Rachas (Streaks)**: Contador de días consecutivos accediendo o aprendiendo.
    - **Puntos/XP**: Ganancia de puntos por ver vídeos, subir técnicas o interactuar.
    - **Logros/Insignias**: Recompensas visuales por hitos (ej. "Cinturón blanco estudioso").

### Procesamiento de Vídeo (Opcional)
- Recorte de duración.
- Generación de miniaturas.
- Ajustes básicos de edición.

### Recomendación de Contenido
- Sistema basado en filtrado colaborativo e historial de usuario.

---

## 3. Planificación (Sprints)

### Sprint 1 — Base Funcional
**Objetivo**: MVP (Producto Mínimo Viable) de la red social.
- **Backend**: Auth JWT, CRUD de usuarios/vídeos, Persistencia BD.
- **Frontend**: Login, Feed básico, Subida de vídeos, Reproductor.
- **Entregable**: Usuarios pueden registrarse, subir y ver vídeos.

### Sprint 2 — Búsqueda Inteligente y Análisis IA (v1)
**Objetivo**: Potenciar el descubrimiento de contenido.
- **Gestión de Técnicas**: Búsqueda por texto y tags.
- **IA Video Analysis**: Integración con Gemini para auto-etiquetado (v1).
- **[NUEVO] Chat IA (v1)**: Implementación básica de búsqueda semántica o RAG (Retrieval-Augmented Generation) sobre la base de datos de técnicas.
- **Entregable**: Vídeos auto-etiquetados y buscador conversacional beta.

### Sprint 3 — Social, Gamificación y "Técnica del Día"
**Objetivo**: Fomentar la retención y el hábito de uso.
- **Social**: Likes, comentarios, seguir usuarios.
- **[NUEVO] Módulo de Aprendizaje**:
    - Implementar sección "Técnica del Día" (lógica de selección).
    - Sistema de Rachas y Puntos (Backend + UI).
- **Entregable**: Interacción social completa y sistema de gamificación activo.

### Sprint 4 — Recomendación, Mejoras IA y Pulido
**Objetivo**: Refinamiento y funcionalidades avanzadas.
- **Recomendación (v2)**: Algoritmo personalizado para el feed y la "Técnica del Día".
- **IA Mejoras**: Refinamiento de prompts para análisis y chat.
- **Procesado de vídeo**: Recorte y miniaturas (si es viable).
- **Calidad**: Tests, manejo de errores, documentación.

---

## 4. Riesgos y Mitigación

### R1. Precisión del Análisis de Vídeo
- **Riesgo**: La IA no identifica correctamente técnicas complejas.
- **Mitigación**: Uso como herramienta de apoyo (sugerencia), edición manual permitida.

### R2. Dependencia de APIs Externas
- **Riesgo**: Costes o cambios en Gemini/Cloud APIs.
- **Mitigación**: Diseño modular para cambiar de proveedor, uso de capas gratuitas, cacheo agresivo.

### [NUEVO] R3. Alucinaciones del Chat IA
- **Riesgo**: El chat responde con información incorrecta o inventada sobre técnicas.
- **Mitigación**: 
    - Restringir el contexto del chat estrictamente a la información de la base de datos (RAG estricto).
    - Incluir disclaimers de "generado por IA".
    - Permitir a usuarios reportar respuestas incorrectas.

### [NUEVO] R4. Complejidad del Sistema de Recomendación
- **Riesgo**: La "Técnica del Día" personalizada no es relevante para el usuario.
- **Mitigación**: Empezar con reglas simples (ej. basadas en cinturón) antes de modelos de ML complejos.
