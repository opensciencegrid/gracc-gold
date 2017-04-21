from distutils.core import setup

setup(name="gracc-gold",
      version="1.0",
      author="Mats Rynge",
      author_email="rynge@isi.edu",
      description="Script for synchronizing OSG GRACC and GOLD",
      package_dir={"": "src"},
      packages=["gracc_gold"],

      scripts = ['src/gracc-gold'],

      #data_files=[("/etc/cron.d", ["config/gracc-gold.cron"]),
      #      ("/etc/gracc-gold", ["config/gracc-gold.cfg.example"]),
      #      ("/etc/logrotate.d", ["config/gracc-gold.logrotate"]),
      #    ],

     )

