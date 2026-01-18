# 🌫️ SGN Controls – PM Monitoring Dashboard

<div align="center">

![PM Monitoring Dashboard](https://img.shields.io/badge/PM-Monitoring-blue?style=for-the-badge&logo=environment&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)

**A real-time environmental monitoring dashboard for particulate matter (PM1, PM2.5, PM4, PM10, TSP)**

[Demo](https://sgncontrols.com) • [Documentation](#-installation) • [API Reference](#-api--routes) • [Contact](#-contact)

</div>

---

## ✨ Features

<table>
<tr>
<td>

📡 **Real-time Data**
- MQTT & TSI API integration
- Live WebSocket updates
- Multi-device monitoring

</td>
<td>

📊 **Visualization**
- Interactive Chart.js graphs
- Historical data analysis
- Real-time value display

</td>
</tr>
<tr>
<td>

🔔 **Smart Alerts**
- Customizable thresholds
- GPIO relay control
- System notifications

</td>
<td>

🛠️ **Admin Panel**
- User management
- Device configuration
- Data source control

</td>
</tr>
</table>

### 🎯 Core Capabilities

> 🔐 **Secure Authentication** • 📤 **CSV Export** • 🌗 **Dark Mode** • 📱 **Responsive Design**

---

## 🏗️ Architecture

```mermaid
graph TB
    A[MQTT Devices] -->|Real-time Data| B[Flask Backend]
    C[TSI API] -->|Polling| B
    B --> D[PostgreSQL Database]
    B --> E[WebSocket Server]
    E --> F[Dashboard Frontend]
    B --> G[Admin Panel]
    H[Nginx Proxy] --> B
    I[Certbot SSL] --> H
```

---

## 🚀 Tech Stack

<div align="center">

| **Category** | **Technologies** |
|:------------:|:----------------:|
| **Backend** | ![Flask](https://img.shields.io/badge/-Flask-000000?logo=flask&logoColor=white) ![Gunicorn](https://img.shields.io/badge/-Gunicorn-199848?logo=gunicorn&logoColor=white) ![Socket.IO](https://img.shields.io/badge/-Socket.IO-010101?logo=socket.io&logoColor=white) |
| **Frontend** | ![Bootstrap](https://img.shields.io/badge/-Bootstrap-7952B3?logo=bootstrap&logoColor=white) ![Chart.js](https://img.shields.io/badge/-Chart.js-FF6384?logo=chart.js&logoColor=white) ![JavaScript](https://img.shields.io/badge/-JavaScript-F7DF1E?logo=javascript&logoColor=black) |
| **Database** | ![PostgreSQL](https://img.shields.io/badge/-PostgreSQL-4169E1?logo=postgresql&logoColor=white) |
| **Infrastructure** | ![AWS EC2](https://img.shields.io/badge/-AWS%20EC2-FF9900?logo=amazon-aws&logoColor=white) ![Nginx](https://img.shields.io/badge/-Nginx-009639?logo=nginx&logoColor=white) ![Let's Encrypt](https://img.shields.io/badge/-Let's%20Encrypt-003A70?logo=letsencrypt&logoColor=white) |

</div>

---

## 📂 Project Structure

```
PM-Monitoring-Dashboard/
├── 🐍 app.py                  # Main Flask application
├── 📄 templates/              # Jinja2 HTML templates
│   ├── dashboard.html         # Main monitoring interface
│   ├── admin.html             # Admin control panel
│   └── login.html             # Authentication page
├── 🎨 static/                 # Frontend assets
│   ├── styles.css             # Custom styling
│   └── script.js              # Dashboard logic
├── 📋 requirements.txt        # Python dependencies
└── 📖 README.md              # This file
```

---

## ⚡ Quick Start

### 1️⃣ Clone & Setup

```bash
# Clone the repository
git clone https://github.com/SGNControls/PM-Monitoring-Dashboard.git
cd PM-Monitoring-Dashboard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2️⃣ Environment Configuration

Create a `.env` file in the project root:

```env
FLASK_SECRET_KEY="your_super_secret_key_here"
DATABASE_URL="postgresql://username:password@localhost/pm_monitoring"
MQTT_BROKER="your.mqtt.broker.ip"
MQTT_USERNAME="mqtt_username"
MQTT_PASSWORD="mqtt_password"
FLASK_HOST="0.0.0.0"
FLASK_PORT="5000"
```

### 3️⃣ Database Setup

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt update && sudo apt install postgresql postgresql-contrib -y

# Create database
sudo -u postgres createdb pm_monitoring
sudo -u postgres createuser --interactive
```

### 4️⃣ Run the Application

```bash
# Development
python app.py

# Production
gunicorn -k eventlet -w 1 app:app --bind 0.0.0.0:5000
```

🎉 **Visit** `http://localhost:5000` to see your dashboard!

---

## 🌐 Production Deployment

### Railway Deployment (Recommended)

Railway provides a simple, scalable cloud platform for deploying your PM Monitoring Dashboard.

#### 🚀 Quick Railway Deploy

1. **Connect Repository**
   ```bash
   # Push your code to GitHub/GitLab
   git add .
   git commit -m "Railway deployment configuration"
   git push origin main
   ```

2. **Deploy on Railway**
   - Go to [Railway.app](https://railway.app) and sign up/login
   - Click "New Project" → "Deploy from GitHub"
   - Select your repository
   - Railway will automatically detect and use the configuration files

3. **Database Setup**
   - Railway automatically provisions PostgreSQL
   - The `DATABASE_URL` environment variable is set automatically
   - No additional database configuration needed!

4. **Environment Variables**
   Railway automatically detects these from your code:
   - `SECRET_KEY` - Auto-generated secure key
   - `DATABASE_URL` - PostgreSQL connection string
   - `PORT` - Dynamic port assignment

5. **Verify Deployment**
   ```bash
   # Test locally first
   python test_deployment.py

   # Check Railway logs for any issues
   ```

#### Railway Configuration Files

The following files are automatically configured for Railway:

- **`railway.json`** - Railway-specific deployment settings
- **`Procfile`** - Process management for Railway
- **`Dockerfile`** - Containerized deployment (optional)
- **`requirements.txt`** - Python dependencies
- **`.env.example`** - Environment variable documentation

#### Railway Features Used

- ✅ **Automatic PostgreSQL** - Database provisioning
- ✅ **Health Checks** - Automatic monitoring
- ✅ **SSL Certificates** - Free HTTPS included
- ✅ **WebSocket Support** - Real-time data streaming
- ✅ **Auto-scaling** - Scales with traffic
- ✅ **Environment Variables** - Secure configuration
- ✅ **Build Caching** - Faster deployments

#### WebSocket Configuration

Railway requires specific configuration for WebSocket connections:

- **`railway.json`** - Enables `websocketSupport: true`
- **`entrypoint.sh`** - Proper port handling for Railway
- **SocketIO Config** - Railway-specific CORS and timeout settings
- **Docker Build** - Uses Dockerfile builder with WebSocket support

**WebSocket Features:**
- Real-time sensor data updates
- Live chart streaming
- Device status notifications
- Multi-user room support

### AWS EC2 Setup (Alternative)

```bash
# System packages
sudo apt update
sudo apt install python3-venv python3-pip postgresql nginx git certbot python3-certbot-nginx -y

# Clone and setup as above, then configure Nginx
sudo nano /etc/nginx/sites-available/pm-monitoring
```

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

#### SSL Certificate

```bash
sudo ln -s /etc/nginx/sites-available/pm-monitoring /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## 🔌 API Reference

<details>
<summary><b>🔐 Authentication Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/login` | User authentication |
| `GET` | `/logout` | End user session |
| `GET/POST` | `/change_password` | Update user password |

</details>

<details>
<summary><b>📊 Data Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/data` | Current & historical PM readings |
| `GET` | `/api/export_csv` | Download data as CSV |
| `GET` | `/dashboard` | Main monitoring interface |

**Example Response:**
```json
{
  "sensor": {
    "pm1": 0.04,
    "pm2_5": 0.08,
    "pm4": 0.09,
    "pm10": 0.15,
    "tsp": 0.18,
    "timestamp": "2025-07-19T13:01:00Z"
  },
  "status": {
    "system": "operational",
    "relay_state": "OFF",
    "thresholds": {
      "pm2.5": 0.05,
      "pm10": 0.09
    }
  }
}
```

</details>

<details>
<summary><b>🛠️ Admin Endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin` | Admin control panel |
| `GET/POST` | `/api/admin/users` | User management |
| `PUT/DELETE` | `/api/admin/users/<id>` | Edit/remove users |
| `GET/POST` | `/api/admin/devices` | Device management |
| `GET/POST` | `/api/admin/data_sources` | Configure data sources |

</details>

---

## 📊 Dashboard Features

### Real-time Monitoring
- **Live Charts**: PM1, PM2.5, PM4, PM10, TSP visualization
- **Current Values**: Instant readings with color-coded status
- **Historical Data**: Trend analysis with zoom capabilities

### Smart Controls
- **Device Selection**: Multi-device dropdown switching
- **Threshold Management**: Custom alert levels
- **Relay Control**: GPIO device automation
- **Data Export**: CSV download with date filtering

### User Experience
- **Responsive Design**: Mobile and desktop optimized
- **Dark Mode**: Eye-friendly night viewing
- **Real-time Updates**: WebSocket-powered live data
- **Secure Access**: Role-based authentication

---

## 🔄 Data Flow

```mermaid
sequenceDiagram
    participant D as MQTT Device
    participant F as Flask Backend
    participant P as PostgreSQL
    participant W as WebSocket
    participant B as Browser

    D->>F: Publish PM data
    F->>P: Store readings
    F->>W: Broadcast update
    W->>B: Live chart update
    
    Note over B: User sees real-time data
```

---

## 🎯 Use Cases

<div align="center">

| 🏭 **Industrial** | 🏫 **Research** | 🚛 **Mobile** | 🌍 **Environmental** |
|:-----------------:|:---------------:|:-------------:|:--------------------:|
| Factory monitoring | Lab experiments | Field studies | Air quality stations |
| Dust control | Equipment testing | Remote sensing | Pollution tracking |
| Compliance reporting | Data collection | Mobile labs | Health monitoring |

</div>

---

## 🛡️ Security Features

- 🔐 **Password Hashing**: SHA256 with salt
- 🎫 **Session Management**: Flask-Login integration
- 🔒 **HTTPS Encryption**: Let's Encrypt certificates
- 👥 **User Isolation**: Scoped data access
- 🚨 **Input Validation**: SQL injection prevention

---

## 🗺️ Roadmap

### 🎯 Coming Soon
- [ ] 📧 Email/SMS alert notifications
- [ ] 👥 Advanced user roles (Viewer/Technician/Admin)
- [ ] 📈 Monthly analytics reports
- [ ] 🔄 Offline data synchronization

### 🚀 Future Vision
- [ ] 🗺️ Geographic mapping integration
- [ ] 🤖 Machine learning predictions
- [ ] 📱 Mobile application
- [ ] ☁️ Multi-cloud deployment

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📞 Support & Contact

<div align="center">

**SGN Controls**

[![Website](https://img.shields.io/badge/Website-sgncontrols.com-blue?style=for-the-badge&logo=google-chrome&logoColor=white)](https://sgncontrols.com)
[![Email](https://img.shields.io/badge/Email-contact@sgncontrols.com-red?style=for-the-badge&logo=gmail&logoColor=white)](mailto:contact@sgncontrols.com)

**Need Help?**
- 📖 [Documentation](docs/)
- 🐛 [Report Issues](issues/)
- 💬 [Discussions](discussions/)

</div>

---

## 📄 License

<div align="center">

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with ❤️ by SGN Controls**

⭐ **Star this repository if it helped you!**

</div>
#   u k _ p m _ m o n i t o r i n g 
 
