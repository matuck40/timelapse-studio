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

// Se o texto corresponde a uma pasta que ja existe em _brutos/ (criada, por exemplo,
// pelo atalho do iPhone com acento), usa o nome exato dela: normalizar criaria uma
// pasta irma e a skill do reel nao acharia o timelapse junto dos clipes.
function escolherPeca(texto, existentes) {
  const chave = normalizarPeca(texto);
  if (!chave) return '';
  return (existentes || []).find((nome) => normalizarPeca(nome) === chave) ?? chave;
}

if (typeof module !== 'undefined') module.exports = { normalizarPeca, escolherPeca };
