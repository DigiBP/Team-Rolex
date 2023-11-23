%%bash
# If your project has a 'requirements.txt' file, we'll install it here.
if test -f requirements.txt
  then
    pip install -r ./requirements.txt
  else echo "There's no requirements.txt, so nothing to install."
fi