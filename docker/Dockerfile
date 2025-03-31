FROM bmeares/meerschaum

USER root
RUN apt-get update && apt-get upgrade -y && apt-get install wget gpg -y
# RUN apt-get install chromium -y
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
RUN apt-get update && apt-get install google-chrome-stable -y
# RUN apt-get update && apt-get upgrade -y && \
  # apt install dirmngr ca-certificates software-properties-common apt-transport-https wget -y && \
  # wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | gpg --dearmor | tee /usr/share/keyrings/packages.mozilla.org.gpg > /dev/null && \
  # echo "deb [signed-by=/usr/share/keyrings/packages.mozilla.org.gpg] https://packages.mozilla.org/apt mozilla main" | tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null && \
  # apt-get update && apt-get install firefox -y

USER meerschaum
RUN mrsm install plugin compose
COPY --chown=meerschaum:meerschaum ./ /app
WORKDIR /app
RUN mrsm compose init

ENTRYPOINT ["/app/docker/bootstrap.sh"]
