document.addEventListener('DOMContentLoaded', function() {
    // Referencias a los elementos del DOM
    const jsonSelect = document.getElementById("jsonSelect");
    const fileDateInfo = document.getElementById("fileDateInfo");
    const selectedFileDateSpan = document.getElementById("selectedFileDate");
    const resultadoDiv = document.getElementById("resultado-validacion");
    const formularioValidacion = document.getElementById("formulario-validacion");
    const processSelect = document.getElementById('processSelect'); // Select para el proceso
    const fileDateSelect = document.getElementById('file_date'); // Select para la fecha del archivo (FechaValidacion)

    // --- 1. Event Listener para jsonSelect (para mostrar la fecha del JSON si existe y actualizar select de fechas) ---
    if (jsonSelect) { // Asegurarse de que el elemento existe
        jsonSelect.addEventListener("change", () => {
            const selectedOption = jsonSelect.options[jsonSelect.selectedIndex];
            // Se asume que el backend (ej. /api/json_files) adjunta un atributo 'data-fecha' a las opciones del JSON
            const fechaPlantilla = selectedOption.getAttribute("data-fecha");

            if (fechaPlantilla) {
                selectedFileDateSpan.textContent = fechaPlantilla;
                fileDateInfo.style.display = "block";
            } else {
                fileDateInfo.style.display = "none";
                selectedFileDateSpan.textContent = ""; // Limpiar fecha anterior
            }
            // Llama a actualizarFechas para poblar el <select id="file_date">
            actualizarFechas();
        });
    }

    // --- 2. Event Listener para formularioValidacion (envío de formulario vía AJAX) ---
    if (formularioValidacion) { // Asegurarse de que el elemento existe
        formularioValidacion.addEventListener("submit", async (e) => { // Usar async/await para mejor legibilidad
            e.preventDefault(); // Prevenir el envío tradicional del formulario

            const formData = new FormData(formularioValidacion); // Esto recopila todos los campos, incluyendo fecha_inicio y fecha_fin

            resultadoDiv.innerHTML = `<div class="alert alert-info">Validando archivo, por favor espera...</div>`;

            // Opcional: Para depuración, puedes ver los datos que se enviarán:
            // for (let [key, value] of formData.entries()) {
            //     console.log(`${key}: ${value}`);
            // }

            try {
                const response = await fetch("/api/validar", {
                    method: "POST",
                    body: formData, // Envía el FormData directamente
                });

                if (!response.ok) {
                    // Si la respuesta HTTP no es 2xx, lanzar un error para que lo capture el bloque .catch
                    const errorText = await response.text(); // Intentar obtener el texto de la respuesta de error
                    throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
                }

                const data = await response.json(); // Esperar la respuesta JSON

                resultadoDiv.innerHTML = ""; // Limpiar contenido anterior
                let html = '';
                if (data.status === "success" || data.status === "success_empty_sheet") {
                    const alertType = data.status === "success" ? "alert-success" : "alert-warning";
                    html = `<div class="alert ${alertType} feedback-message">${data.message}</div>`;
                } else {
                    html = `<div class="alert alert-danger feedback-message"><strong>${data.message}</strong><ul>`;
                    if (data.errores && Array.isArray(data.errores)) { // Seguridad: Verifica que data.errores sea un array
                        data.errores.forEach((error) => {
                            // Mostrar errores de forma más legible
                            html += `<li><strong>Hoja: ${error.hoja || 'N/A'}, Fila: ${error.fila || 'N/A'}:</strong> ${error.errores || 'Error desconocido en detalle.'}</li>`;
                        });
                    } else {
                        html += `<li>Error desconocido: No se proporcionaron detalles de errores o el formato es incorrecto.</li>`;
                    }
                    html += "</ul></div>";
                }
                resultadoDiv.innerHTML = html;

            } catch (error) {
                console.error("Error al validar:", error);
                resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al procesar la solicitud: ${error.message}</div>`;
            }
        });
    }

    // --- 3. Funciones auxiliares para cargar selects dinámicamente ---

    // Función para filtrar los JSONs según el proceso seleccionado
    if (processSelect) { // Asegurarse de que el elemento existe
        processSelect.addEventListener('change', filtrarJsonPorProceso);
        // Opcional: Llama a la función al cargar la página si ya hay un proceso seleccionado (ej. si se refrescó la página)
        if (processSelect.value) {
            filtrarJsonPorProceso();
        }
    }

    async function filtrarJsonPorProceso() {
        const procesoId = processSelect.value;
        // Asegurarse de que los elementos necesarios existan antes de manipularlos
        if (!jsonSelect || !fileDateSelect || !selectedFileDateSpan) return;

        jsonSelect.innerHTML = '<option value="" disabled selected>Cargando plantillas...</option>';
        jsonSelect.disabled = true;
        fileDateSelect.innerHTML = '<option value="" disabled selected>Selecciona una fecha</option>';
        fileDateSelect.disabled = true;
        selectedFileDateSpan.textContent = ''; // Limpiar la fecha del archivo seleccionado

        if (!procesoId) {
            jsonSelect.innerHTML = '<option value="" disabled selected>Seleccione un proceso primero</option>';
            jsonSelect.disabled = false;
            return;
        }

        try {
            const response = await fetch(`/api/json_files?proceso_id=${procesoId}`); // Endpoint para obtener archivos JSON por ID de proceso
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            jsonSelect.innerHTML = '<option value="" disabled selected>Selecciona un archivo...</option>';
            if (data.status === 'success' && data.plantillas && Array.isArray(data.plantillas) && data.plantillas.length > 0) {
                data.plantillas.forEach(plantilla => {
                    const option = document.createElement('option');
                    option.value = plantilla.NombrePlantilla;
                    option.textContent = plantilla.NombrePlantilla;
                    // Si el backend envía una 'fecha' para la plantilla, se añade como 'data-fecha'
                    if (plantilla.fecha) {
                        option.setAttribute("data-fecha", plantilla.fecha);
                    }
                    jsonSelect.appendChild(option);
                });
            } else {
                jsonSelect.innerHTML = '<option value="" disabled selected>No hay plantillas disponibles</option>';
            }
            jsonSelect.disabled = false;

        } catch (error) {
            console.error('Error al cargar plantillas JSON:', error);
            resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al cargar plantillas: ${error.message}</div>`;
            jsonSelect.innerHTML = '<option value="" disabled selected>Error al cargar plantillas</option>';
            jsonSelect.disabled = false;
        }
    }

    // Función para actualizar las fechas disponibles según el JSON seleccionado (para el select 'file_date')
    if (jsonSelect) { // Asegurarse de que el elemento existe
        jsonSelect.addEventListener('change', actualizarFechas);
    }

    async function actualizarFechas() {
        const nombrePlantilla = jsonSelect.value;
        if (!fileDateSelect) return; // Asegurar que el elemento existe

        fileDateSelect.innerHTML = '<option value="" disabled selected>Cargando fechas...</option>';
        fileDateSelect.disabled = true;

        if (!nombrePlantilla) {
            fileDateSelect.innerHTML = '<option value="" disabled selected>Selecciona un archivo JSON primero</option>';
            fileDateSelect.disabled = false;
            return;
        }

        try {
            const response = await fetch(`/obtener_fechas_json?nombre_plantilla=${encodeURIComponent(nombrePlantilla)}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            fileDateSelect.innerHTML = '<option value="" disabled selected>Selecciona una fecha</option>';
            if (data && data.fechas && Array.isArray(data.fechas)) {
                data.fechas.forEach(fecha => {
                    const option = document.createElement("option");
                    option.value = fecha; // La fecha ya debe estar en el formato deseado (YYYY-MM-DD)
                    option.textContent = fecha;
                    fileDateSelect.appendChild(option);
                });
            } else {
                console.warn("No hay fechas disponibles para esta plantilla o formato de datos incorrecto.");
                fileDateSelect.innerHTML = '<option value="" disabled selected>No hay fechas disponibles</option>';
            }
            fileDateSelect.disabled = false;

        } catch (error) {
            console.error("Error al obtener fechas:", error);
            resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al obtener las fechas del archivo: ${error.message}</div>`;
            fileDateSelect.innerHTML = '<option value="" disabled selected>Error al cargar fechas</option>';
            fileDateSelect.disabled = false;
        }
    }

    // Escuchar cambios en el select de file_date para mostrar la fecha seleccionada en el span
    if (fileDateSelect) { // Asegurarse de que el elemento existe
        fileDateSelect.addEventListener('change', function() {
            selectedFileDateSpan.textContent = fileDateSelect.value;
        });
    }
});