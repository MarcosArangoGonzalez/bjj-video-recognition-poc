# Guía Paso a Paso: Configurar Google Cloud Video Intelligence

## Paso 1: Crear Cuenta de Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Inicia sesión con tu cuenta de Google
3. Si es tu primera vez, acepta los términos de servicio

> **Nota**: Google Cloud ofrece $300 de crédito gratuito para nuevos usuarios y el Video Intelligence API tiene 1,000 minutos gratis al mes.

---

## Paso 2: Crear un Nuevo Proyecto

1. En la parte superior, haz clic en el selector de proyectos
2. Clic en **"Nuevo proyecto"**
3. Nombre del proyecto: `bjj-video-recognition` (o el que prefieras)
4. Clic en **"Crear"**
5. Espera unos segundos a que se cree el proyecto
6. **Selecciona el proyecto** desde el selector de proyectos

---

## Paso 3: Habilitar la API de Video Intelligence

1. En el menú lateral (☰), ve a **"APIs y servicios"** → **"Biblioteca"**
2. En el buscador, escribe: `Video Intelligence API`
3. Haz clic en **"Cloud Video Intelligence API"**
4. Clic en el botón **"HABILITAR"**
5. Espera a que se habilite (tarda unos segundos)

---

## Paso 4: Configurar Facturación (Requerido)

> **Importante**: Aunque uses el tier gratuito, Google Cloud requiere una tarjeta para verificación.

1. En el menú lateral, ve a **"Facturación"**
2. Clic en **"Vincular una cuenta de facturación"**
3. Sigue los pasos para añadir tu tarjeta
4. **No te preocupes**: No te cobrarán mientras estés dentro del tier gratuito (1,000 min/mes)

---

## Paso 5: Crear Service Account

1. En el menú lateral (☰), ve a **"IAM y administración"** → **"Cuentas de servicio"**
2. Clic en **"+ CREAR CUENTA DE SERVICIO"**
3. Completa los datos:
   - **Nombre**: `video-analysis-service`
   - **ID**: se genera automáticamente
   - **Descripción**: `Service account for BJJ video analysis`
4. Clic en **"CREAR Y CONTINUAR"**

---

## Paso 6: Asignar Permisos

1. En "Otorgar acceso a esta cuenta de servicio al proyecto":
2. Selecciona el rol: **"Cloud Video Intelligence Admin"**
   - Escribe "video" en el buscador para encontrarlo rápido
3. Clic en **"CONTINUAR"**
4. Clic en **"LISTO"** (puedes omitir el paso 3)

---

## Paso 7: Crear y Descargar la Clave JSON

1. En la lista de cuentas de servicio, encuentra la que acabas de crear
2. Haz clic en los **tres puntos (⋮)** a la derecha
3. Selecciona **"Administrar claves"**
4. Clic en **"AGREGAR CLAVE"** → **"Crear clave nueva"**
5. Selecciona tipo: **JSON**
6. Clic en **"CREAR"**
7. **Se descargará automáticamente** un archivo JSON (guárdalo bien)

---

## Paso 8: Configurar las Credenciales en tu Proyecto

### Opción A: Variable de Entorno (Recomendada)

```bash
# Mueve el archivo descargado a una ubicación segura
mv ~/Descargas/tu-proyecto-xxxxx.json ~/gcp-credentials.json

# Configura la variable de entorno
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gcp-credentials.json"

# Para que persista, añádelo a tu ~/.bashrc o ~/.zshrc
echo 'export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gcp-credentials.json"' >> ~/.bashrc
source ~/.bashrc
```

### Opción B: Archivo en el Proyecto

```bash
# Copia el archivo a src/main/resources/
cp ~/Descargas/tu-proyecto-xxxxx.json \
   /home/marcos/.gemini/antigravity/playground/white-lagoon/bjj-video-recognition-poc/src/main/resources/gcp-credentials.json
```

---

## Paso 9: Obtener el Project ID

1. En Google Cloud Console, ve al **Dashboard**
2. Copia el **"ID del proyecto"** (no el nombre, el ID)
3. Configúralo:

```bash
export GOOGLE_CLOUD_PROJECT_ID="tu-project-id-aqui"
```

O actualiza el `application.yml`:
```yaml
google:
  cloud:
    project-id: tu-project-id-aqui
```

---

## Paso 10: Verificar la Configuración

```bash
# Reinicia el servidor Spring Boot
cd /home/marcos/.gemini/antigravity/playground/white-lagoon/bjj-video-recognition-poc
mvn spring-boot:run
```

Ahora intenta subir un video de nuevo. ¡Debería funcionar!

---

## Troubleshooting

### Error: "Credentials not found"
- Verifica que `GOOGLE_APPLICATION_CREDENTIALS` apunte al archivo correcto
- Verifica que el archivo JSON existe en esa ruta

### Error: "Permission denied"
- Asegúrate de haber asignado el rol "Cloud Video Intelligence Admin"
- Espera 1-2 minutos para que los permisos se propaguen

### Error: "API not enabled"
- Ve a la biblioteca de APIs y verifica que "Cloud Video Intelligence API" esté habilitada

---

## Costos

- **Gratis**: Primeros 1,000 minutos/mes
- **Después**: ~$0.10 por minuto
- **Recomendación**: Usa videos cortos (< 1 min) durante desarrollo

---

## Seguridad

⚠️ **IMPORTANTE**: 
- **NO** subas el archivo JSON a GitHub
- Añade `gcp-credentials.json` a tu `.gitignore`
- Mantén el archivo seguro (contiene acceso a tu proyecto)

---

¿Necesitas ayuda con algún paso específico?
