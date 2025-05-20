function mostrarNombreArchivo(input) {
    const nombreArchivo = document.getElementById('nombreArchivo');
    if (input.files && input.files[0]) {
        nombreArchivo.textContent = "Archivo seleccionado: " + input.files[0].name;
        nombreArchivo.classList.remove('text-muted');
        nombreArchivo.classList.add('text-success', 'fw-bold');
    } else {
        nombreArchivo.textContent = "Sin archivos seleccionados";
        nombreArchivo.classList.remove('text-success', 'fw-bold');
        nombreArchivo.classList.add('text-muted');
    }
}
