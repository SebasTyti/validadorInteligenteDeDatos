document.addEventListener('DOMContentLoaded', function () {
    // Variables globales
    let originalData;
    let uploaded_excel;
    let regexOptionsByType;
    let hojaSeleccionada;

    // Obtener los datos iniciales desde los atributos data
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

            hojaSeleccionada = rootElement.dataset.hojaSeleccionada || "";

        } catch (error) {
            console.error("Error al parsear los datos iniciales:", error);
            showError("Error al cargar los datos iniciales.", "error-message");
            return;
        }
    } else {
        console.error("No se encontró el elemento con id 'data-container' para cargar los datos iniciales.");
        showError("No se pudieron cargar los datos iniciales.", "error-message");
        return;
    }

    // Función para mostrar errores
    function showError(message, elementId = null) {
        if (elementId) {
            document.getElementById(elementId).textContent = message;
        } else {
            const errorDiv = document.getElementById("error-message");
            errorDiv.textContent = message;
            errorDiv.style.display = "block";
            setTimeout(() => errorDiv.style.display = "none", 5000);
        }
    }

    // Filtra opciones de regex según el tipo seleccionado
    function filterRegexOptions() {
        const table = document.getElementById('editableTable');
        if (!table) return;

        table.querySelectorAll('tbody tr').forEach(row => {
            const typeSelect = row.querySelector('.type-select');
            const regexSelect = row.querySelector('.regex-select');
            if (!typeSelect || !regexSelect) return;

            const selectedType = typeSelect.value;

            const hasOptionsForType = regexOptionsByType && regexOptionsByType[selectedType] && regexOptionsByType[selectedType].length > 0;
            regexSelect.disabled = !hasOptionsForType;

            Array.from(regexSelect.options).forEach(option => {
                if (option.value === "") {
                    option.hidden = false;
                    return;
                }

                const optionType = option.dataset.type;
                option.hidden = optionType !== selectedType;
            });

            if (regexSelect.value !== "" &&
                regexSelect.selectedOptions.length > 0 &&
                regexSelect.selectedOptions[0].dataset.type !== selectedType) {
                regexSelect.value = "";
            }
        });
    }

    // Extrae datos editados de la tabla
    function getEditedData() {
        const table = document.getElementById("editableTable");
        if (!table) return [];

        const edited = [];
        const rows = table.querySelector("tbody").querySelectorAll("tr");

        rows.forEach((row, index) => {
            const cells = row.querySelectorAll("td");
            if (cells.length !== 4) {
                showError(`Error: La fila ${index + 1} tiene un número incorrecto de celdas.`, "error-message");
                return;
            }

            const nombreCell = cells[0];
            const typeSelect = cells[1].querySelector("select");
            const requiredSelect = cells[2].querySelector("select");
            const regexSelect = cells[3].querySelector("select");

            if (!nombreCell || !typeSelect || !requiredSelect || !regexSelect) {
                showError(`Error: No se encontraron los elementos select en la fila ${index + 1}.`, "error-message");
                return;
            }

            const nombre = nombreCell.innerText.trim();
            if (!nombre) {
                showError(`Error: El campo 'Nombre' en la fila ${index + 1} es obligatorio.`, "error-message");
                return;
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

    // Aplicar filtros de regex al cargar
    filterRegexOptions();

    // Reaplicar filtro al cambiar el tipo de campo
    const table = document.getElementById('editableTable');
    if (table) {
        table.addEventListener('change', function (e) {
            if (e.target.classList.contains('type-select')) {
                filterRegexOptions();
            }
        });
    }

    // Configurar evento del botón "Cargar Plantilla"
    const cargarBtn = document.getElementById("cargarBtn");
    if (cargarBtn) {
        cargarBtn.addEventListener("click", function () {
            const destinoSelect = document.getElementById("destino");
            const idProcesoAdmin = destinoSelect.value;

            if (!idProcesoAdmin) {
                showError("Por favor seleccione un destino para la plantilla (Recursos humanos o Dirección Tecnológica)", "destino-error");
                return;
            } else {
                showError("", "destino-error");
            }

            const editedData = getEditedData();
            if (!editedData || editedData.length === 0) {
                showError("Por favor, corrija los errores en la tabla antes de cargar.", "error-message");
                return;
            }

            const payload = {
                "editado": editedData,
                "idProcesoAdmin": idProcesoAdmin,
                "uploaded_excel": uploaded_excel,
                "hoja_seleccionada": hojaSeleccionada
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