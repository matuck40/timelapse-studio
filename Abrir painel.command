#!/bin/zsh
# Duplo clique abre o painel. Feche esta janela para parar o servidor e a fila.
cd -- "${0:A:h}" || exit 1
PYTHON=$(command -v python3)
if [[ -z "$PYTHON" ]]; then
  print 'Python 3 não encontrado neste Mac.'
  print 'Pressione Enter para fechar.'
  read -r
  exit 1
fi
"$PYTHON" -m timelapse.servidor
print '\nPainel encerrado. Pressione Enter para fechar.'
read -r
