# Bitcoind ZMQ Proxy

## Introduction
This project is a Python-based proxy that forwards ZMQ data from Bitcoin Core over local TCP streams to TLS-wrapped TCP streams connected to a remote server. It now supports forwarding each of the different bitcoind ZMQ subscriptions to their own ports.

## Rationale for Using a TCP Proxy
The TCP proxy setup in this project serves multiple purposes:

1. **TLS Encryption for Secure Transmission:** By forwarding ZeroMQ (ZMQ) data over a TCP stream wrapped in TLS, we ensure that the traffic is encrypted. This prevents unauthorized access and ensures that the data being transmitted is secure and private.

2. **Hostname Utilization:** This method allows for the connection to a remote server using a hostname rather than an IP address.

3. **Simplified Setup:** Establishing a direct ZMQ connection over a TLS-encrypted TCP pipe is complex and not straightforward. Using a TCP proxy to handle the TLS encryption simplifies the process while providing a sufficient level of security and functionality.

## Features
- Proxies ZMQ messages from a remote bitcoind node to local ports
- Supports multiple ZMQ topics (rawblock, rawtx, hashblock, hashtx, sequence)
- Dockerized for easy deployment
- Configurable via environment variables

## Prerequisites
- Docker
- Docker Compose

## Setup and Configuration

1. Clone this repository:
   ```
   git clone https://github.com/austinkelsat/bitcoind-zmq-proxy.git
   cd bitcoind-zmq-proxy
   ```

2. Ensure you have the following files in your project directory:
   - `main.py`
   - `Dockerfile`
   - `docker-compose.yml`
   - `requirements.txt`

3. Edit the `docker-compose.yml` file to set your environment variables:

   - `BITCOIND_HOST`: The hostname of your remote bitcoind node (example: `bcntplorcd.b.voltageapp.io`)
   - `BITCOIND_PORT`: The port of your remote bitcoind node (default: 28332)
   - `ZMQ_RAWBLOCK_PORT`: Local port for rawblock messages (default: 28331)
   - `ZMQ_RAWTX_PORT`: Local port for rawtx messages (default: 28330)
   - `ZMQ_HASHBLOCK_PORT`: Local port for hashblock messages (default: 28329)
   - `ZMQ_HASHTX_PORT`: Local port for hashtx messages (default: 28328)
   - `ZMQ_SEQUENCE_PORT`: Local port for sequence messages (default: 28327)

## Running the Proxy

1. Start the ZMQ proxy:
   ```
   docker-compose up --build
   ```

2. The proxy will now forward ZMQ messages from the remote bitcoind node to the specified local ports.

## Usage Example (Node.js)

```javascript
const zmq = require('zeromq');

async function connectToTopic(port, topic) {
  const sock = new zmq.Subscriber;
  sock.connect(`tcp://localhost:${port}`);
  sock.subscribe(topic);

  console.log(`Subscriber connected to port ${port} for topic ${topic}`);

  for await (const [receivedTopic, msg] of sock) {
    console.log(`Received a message on port ${port}:`);
    console.log('Topic:', receivedTopic.toString());
    console.log('Message:', msg.toString('hex'));
  }
}

async function run() {
  const topics = [
    { port: 28331, topic: 'rawblock' },
    { port: 28330, topic: 'rawtx' },
    { port: 28329, topic: 'hashblock' },
    { port: 28328, topic: 'hashtx' },
    { port: 28327, topic: 'sequence' }
  ];

  for (const { port, topic } of topics) {
    connectToTopic(port, topic);
  }
}

run();
```

## Troubleshooting

1. **No data received**: Ensure that your remote bitcoind node is sending ZMQ messages. Check the Docker container logs for any error messages.

2. **Connection issues**: If you're having trouble connecting to the proxy from your application, make sure you're using the correct IP address. If you're running Docker on a remote machine, you may need to use that machine's IP address instead of `localhost`.

3. **Port conflicts**: If you see errors about ports already being in use, make sure no other services are using the specified ports on your machine.

4. **Performance issues**: If you're experiencing high CPU usage or memory consumption, you may need to adjust the `RCVHWM` (high water mark) setting in the `ZMQHandler` class in `main.py`.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
[MIT License](https://opensource.org/licenses/MIT)

## Acknowledgments
This project is based on the work by [tee8z/zmq_tls_tcp_proxy_example](https://github.com/tee8z/zmq_tls_tcp_proxy_example).