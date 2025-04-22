#!/bin/bash

# Set iDRAC credentials and IP
IDRAC_IP="10.20.30.250"
PASS_FILE="$HOME/.ssh/idrac_pass"
SSH_CMD="sshpass -f $PASS_FILE ssh -o StrictHostKeyChecking=no root@$IDRAC_IP"

# Function to display menu
show_menu() {
    clear
    echo "============================"
    echo " Dell iDRAC Management Menu"
    echo "============================"
    echo "1) Power Cycle (Reboot Server)"
    echo "2) Power Off Server"
    echo "3) Power On Server"
    echo "4) Check Power Status"
    echo "5) Reset iDRAC (Fix Web UI Login Issues)"
    echo "6) Exit"
    echo "============================"
    read -p "Enter your choice [1-6]: " choice
}

# Function to execute selected command
execute_choice() {
    case $choice in
        1)
            echo "Rebooting the server via iDRAC..."
            $SSH_CMD racadm serveraction powercycle
            ;;
        2)
            echo "Shutting down the server (force off)..."
            $SSH_CMD racadm serveraction poweroff
            ;;
        3)
            echo "Powering on the server..."
            $SSH_CMD racadm serveraction powerup
            ;;
        4)
            echo "Checking power status..."
            $SSH_CMD racadm serveraction powerstatus | grep --color -e ON -e OFF
            ;;
        5)
            echo "Resetting iDRAC (this may take a few minutes)..."
            $SSH_CMD racadm racreset
            echo "iDRAC is resetting. Wait a few minutes before accessing the web UI."
            ;;
        6)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo "Invalid choice, please try again."
            ;;
    esac
}

# Main loop
while true; do
    show_menu
    execute_choice
    read -p "Press Enter to continue..." dummy
done

