'use strict';

// O campo Peca vira o nome de uma subpasta de _brutos/: "Ovo de Páscoa" -> "ovo-de-pascoa".
// Mesma regra do atalho do iPhone: minusculas, sem acento, espacos viram hifen; o resto fica.
function normalizarPeca(texto) {
  return String(texto)
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[/:]/g, '')  // quebrariam o caminho
    .trim()
    .replace(/\s+/g, '-')
    .replace(/^\.+/, '');  // ".." subiria uma pasta; ".x" ficaria oculta
}

if (typeof module !== 'undefined') module.exports = { normalizarPeca };
