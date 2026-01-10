# Pika-pika

A Python-based Raspberry Pi voltage logger and live web viewer.

This documentation contains quick links and usage for the project. The full README is included in the repository and the site contains a short guide to the features and a demo page.

- Live UI: `/` (served by the running app)
- Demo UI: `/demo` (mock data — no hardware required)

## Quick start

### Raspberry Pi instructions:
Use the following guide to install and run this code on your pi:
[rpi start guide](./rpi-setup-guide.md)


### Run the demo on your local machine:
```bash
make fresh-install
make dev
```

3. Open `http://<pi-ip>:8000/` or the demo at `http://<pi-ip>:8000/demo`.