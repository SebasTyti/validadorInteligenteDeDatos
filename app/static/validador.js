const jsonSelect = document.getElementById("jsonSelect");
        const fileDateInfo = document.getElementById("fileDateInfo");
        const selectedFileDateSpan = document.getElementById("selectedFileDate");
        const resultadoDiv = document.getElementById("resultado-validacion");
        const formularioValidacion = document.getElementById("formulario-validacion");


        jsonSelect.addEventListener("change", () => {
            const selectedOption = jsonSelect.options[jsonSelect.selectedIndex];
            const fecha = selectedOption.getAttribute("data-fecha");

            if (fecha) {
                selectedFileDateSpan.textContent = fecha;
                fileDateInfo.style.display = "block";
            } else {
                fileDateInfo.style.display = "none";
                selectedFileDateSpan.textContent = ""; // Clear previous date
            }
            actualizarFechas();
        });

        formularioValidacion.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(formularioValidacion);

            resultadoDiv.innerHTML = `<div class="alert alert-info">Validando...</div>`; // Mensaje de carga

            fetch("/api/validar", {   // Asegúrate de que esta ruta coincide con tu backend
                method: "POST",
                body: formData,
            })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then((data) => {
                resultadoDiv.innerHTML = ""; // Clear previous content
                let html = '';
                if (data.status === "success") {
                    html = `<div class="alert alert-success feedback-message">${data.message}</div>`;
                } else if (data.status === "success_empty_sheet") {
                    html = `<div class="alert alert-warning feedback-message">${data.message}</div>`;
                }
                else {
                    html = `<div class="alert alert-danger feedback-message"><strong>${data.message}</strong><ul>`;
                    if (data.errores && Array.isArray(data.errores)) {   // Seguridad: Verifica que data.errores sea un array
                        data.errores.forEach((error) => {
                            html += `<li><strong>Fila ${error.fila}:</strong> ${JSON.stringify(error.errores)}</li>`;
                        });
                    } else {
                        html += `<li>Error desconocido: No se proporcionaron detalles de errores.</li>`;
                    }
                    html += "</ul></div>";
                }
                resultadoDiv.innerHTML = html;
            })
            .catch((error) => {
                console.error("Error al validar:", error);
                resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al procesar la solicitud: ${error.message}</div>`;
            });
        });


        function filtrarJsonPorProceso() {
            const procesoId = document.getElementById("processSelect").value;
            const jsonSelectElement = document.getElementById("jsonSelect");

            jsonSelectElement.innerHTML = '<option value="">Seleccione un archivo...</option>';

            if (procesoId) {
                fetch(`/api/json_files?proceso_id=${procesoId}`)   // Endpoint para obtener archivos JSON por ID de proceso
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const archivos = data.plantillas || data.archivos || [];   //backend
                    if (!Array.isArray(archivos)) {
                        console.error("La respuesta del servidor no es un array:", data);
                        resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error: El servidor devolvió un formato de datos incorrecto.</div>`;
                        return;
                    }
                    archivos.forEach(archivo => {
                        const option = document.createElement("option");
                        option.value = archivo.NombrePlantilla;
                        option.textContent = archivo.NombrePlantilla;
                        if (archivo.fecha) {
                            option.setAttribute("data-fecha", archivo.fecha);
                        }
                        jsonSelectElement.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error("Error al obtener archivos JSON:", error);
                    resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al obtener la lista de archivos: ${error.message}</div>`;
                });
            }
        }

        function actualizarFechas() {
            const nombrePlantilla = jsonSelect.value;
            const fechaSelect = document.getElementById("file_date");
            fechaSelect.innerHTML = '<option value="" disabled selected>Selecciona una fecha</option>';

            if (!nombrePlantilla) return;   // No hacer la petición si no hay plantilla seleccionada

            fetch(`/obtener_fechas_json?nombre_plantilla=${encodeURIComponent(nombrePlantilla)}`) //cambiar el nombre del endpoint si es necesario
            .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                return response.json();
            })
            .then(data => {
                if (data && Array.isArray(data.fechas)) {
                    data.fechas.forEach(fecha => {
                        const option = document.createElement("option");
                        option.value = fecha;
                        option.textContent = fecha;
                        fechaSelect.appendChild(option);
                    });
                }
                else{
                    console.error("La respuesta del servidor no es un array:", data);
                     resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error: El servidor devolvió un formato de datos incorrecto.</div>`;
                }

            })
            .catch(error => {
                console.error("Error al obtener fechas:", error);
                resultadoDiv.innerHTML = `<div class="alert alert-danger feedback-message">Error al obtener las fechas del archivo: ${error.message}</div>`;
            });
        }
    