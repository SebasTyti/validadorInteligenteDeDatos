document.addEventListener('DOMContentLoaded', function () {
    // Variables globales (¡Mejorar esto más adelante!)
    var originalData;
    var uploaded_excel;
    var regexOptionsByType;

    // Obtener los datos iniciales a través de atributos data del elemento raíz
    const rootElement = document.getElementById('data-container');
    if (rootElement) {
    try {
        if (rootElement.dataset.originalJson)
            originalData = JSON.parse(rootElement.dataset.originalJson);
        else
            throw new Error("originalJson vacío");

        if (rootElement.dataset.uploadedExcel)
            uploaded_excel = JSON.parse(rootElement.dataset.uploadedExcel);
        else
            throw new Error("uploadedExcel vacío");

        if (rootElement.dataset.regexOptionsByType)
            regexOptionsByType = JSON.parse(rootElement.dataset.regexOptionsByType);
        else
            throw new Error("regexOptionsByType vacío");
    } catch (error) {
        console.error("Error al parsear los datos iniciales:", error);
        showError("Error al cargar los datos iniciales.", "error-message");
        return;
    }
}
    else {
        console.error("No se encontró el elemento con id 'data-container' para cargar los datos iniciales.");
        showError("No se pudieron cargar los datos iniciales.", "error-message");
        return;
    }

    // Función para mostrar mensajes de error
    function showError(message, elementId = null) {
        if (elementId) {
            document.getElementById(elementId).textContent = message;
        } else {
            const errorDiv = document.getElementById("error-message");
            errorDiv.textContent = message;
            errorDiv.style.display = "block";
            setTimeout(() => errorDiv.style.display = "none", 5000); // Ocultar después de 5 segundos
        }
    }

    // Función para filtrar las opciones de regex según el tipo seleccionado
    function filterRegexOptions() {
        const table = document.getElementById('editableTable');
        if (!table) return; // Salir si la tabla no existe

        table.querySelectorAll('tbody tr').forEach(row => {
            const typeSelect = row.querySelector('.type-select');
            const regexSelect = row.querySelector('.regex-select');
            if (!typeSelect || !regexSelect) return; // Saltar si no se encuentran los selects

            const selectedType = typeSelect.value;

            // Habilitar o deshabilitar el select de regex según si hay opciones disponibles
            const hasOptionsForType = regexOptionsByType && regexOptionsByType[selectedType] && regexOptionsByType[selectedType].length > 0;
            regexSelect.disabled = !hasOptionsForType;

            // Filtrar opciones mostradas
            Array.from(regexSelect.options).forEach(option => {
                if (option.value === "") {
                    option.hidden = false;
                    return;
                }

                const optionType = option.dataset.type;
                option.hidden = optionType !== selectedType;
            });

            // Si la opción actual no coincide con el tipo, resetearla
            if (regexSelect.value !== "" &&
                regexSelect.selectedOptions.length > 0 && // Verificar si hay opciones seleccionadas
                regexSelect.selectedOptions[0].dataset.type !== selectedType) {
                regexSelect.value = "";
            }
        });
    }

    // Función para obtener los datos editados
    function getEditedData() {
        const table = document.getElementById("editableTable");
        if (!table) return []; // Retornar un array vacío si la tabla no existe

        const edited = [];
        const rows = table.querySelector("tbody").querySelectorAll("tr");

        rows.forEach((row, index) => { // Agregar el índice para los mensajes de error
            const cells = row.querySelectorAll("td");
            if (cells.length !== 4) {
                showError(`Error: La fila ${index + 1} tiene un número incorrecto de celdas.`, "error-message");
                return; // Saltar esta fila
            }

            const nombreCell = cells[0];
            const typeSelect = cells[1].querySelector("select");
            const requiredSelect = cells[2].querySelector("select");
            const regexSelect = cells[3].querySelector("select");

            if (!nombreCell || !typeSelect || !requiredSelect || !regexSelect) {
                showError(`Error: No se encontraron los elementos select en la fila ${index + 1}.`, "error-message");
                return; // Saltar esta fila
            }

            const nombre = nombreCell.innerText.trim();
            if (!nombre) {
                showError(`Error: El campo 'Nombre' en la fila ${index + 1} es obligatorio.`, "error-message");
                return; // Detener el procesamiento si hay un error
            }

            edited.push({
                "Nombre": nombre,
                "Type": typeSelect.value,
                "Required": requiredSelect.value,
                "Regex": regexSelect.value
            });
        });

        return edited;
    }

    // Aplicar filtro inicial
    filterRegexOptions();

    // Escuchar cambios en los selects de tipo
    const table = document.getElementById('editableTable');
    if (table) {
        table.addEventListener('change', function (e) {
            if (e.target.classList.contains('type-select')) {
                filterRegexOptions();
            }
        });
    }

    // Configurar evento del botón de carga
    const cargarBtn = document.getElementById("cargarBtn");
    if (cargarBtn) {
        cargarBtn.addEventListener("click", function () {
            const destinoSelect = document.getElementById("destino");
            const idProcesoAdmin = destinoSelect.value;

            if (!idProcesoAdmin) {
                showError("Por favor seleccione un destino para la plantilla (Recursos humanos o Dirección Tecnológica)", "destino-error");
                return;
            } else {
                showError("", "destino-error"); // Limpiar el mensaje de error si hay uno
            }

            const editedData = getEditedData();
            if (!editedData || editedData.length === 0) {
                // getEditedData ya muestra errores individuales en las filas
                showError("Por favor, corrija los errores en la tabla antes de cargar.", "error-message");
                return;
            }

            const payload = {
                "editado": editedData,
                "idProcesoAdmin": idProcesoAdmin,
                "uploaded_excel": uploaded_excel
            };

            console.log("Payload a enviar:", payload);

            fetch("/guardar_plantilla", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(result => {
                    if (result.success) {
                        alert("Plantilla guardada exitosamente.");
                        window.location.href = result.download_url;
                    } else {
                        showError(result.error, "error-message");
                        console.error("Detalles del error:", result);
                    }
                })
                .catch(error => {
                    console.error("Error de Fetch:", error);
                    showError("Error al enviar los datos al servidor: " + error.message, "error-message");
                });
        });
    }
});