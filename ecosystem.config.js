module.exports = {
  apps: [{
    name: 'rank-api',
    script: 'server.py',
    interpreter: 'python3',
    cwd: '/home/tech/packet_coupang_v1',
    args: '',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      NODE_ENV: 'production'
    },
    error_file: '/home/tech/packet_coupang_v1/logs/error.log',
    out_file: '/home/tech/packet_coupang_v1/logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    exp_backoff_restart_delay: 100,
    max_restarts: 10,
    restart_delay: 1000
  }]
};
