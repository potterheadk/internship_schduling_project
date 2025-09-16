#!/usr/bin/env bash

# Configuration
CONFIG_FILE="$HOME/.config/uma_api_explorer.conf"
API_HOST="http://localhost:3000"
DEFAULT_OUTPUT_DIR="output"
JQ_CMD="jq"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    # Create default configuration
    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat > "$CONFIG_FILE" << EOF
# UMA API Explorer Configuration
TOKEN="<PUT_JWT_HERE>"
API_HOST="http://localhost:3000"
SAVE_RESPONSES=false
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
EOF
    echo -e "${YELLOW}Created default configuration at $CONFIG_FILE${NC}"
fi

# Ensure token is set
if [ "$TOKEN" = "<PUT_JWT_HERE>" ]; then
    echo -e "${RED}Please set your JWT token in $CONFIG_FILE${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v $JQ_CMD &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. Please install it first.${NC}"
    exit 1
fi

# Base URLs
API_URL="http://localhost:3000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function to make API calls
call_api() {
    local endpoint=$1
    local description=$2
    echo -e "${BLUE}=== $description ===${NC}"
    echo "GET $API_URL$endpoint"
    curl -sS -H "Authorization: Bearer $TOKEN" "$API_URL$endpoint" | jq '.'
    echo
}

# Helper function to make API calls with filters
call_api_with_filters() {
    local endpoint=$1
    local description=$2
    shift 2
    local filters=()
    
    # Build query string from remaining args
    for filter in "$@"; do
        filters+=("$filter")
    done
    
    local query=$(printf "&%s" "${filters[@]}")
    query="?${query:1}" # Remove first & and add ?
    
    echo -e "${BLUE}=== $description ===${NC}"
    echo "GET $API_URL$endpoint$query"
    curl -sS -H "Authorization: Bearer $TOKEN" "$API_URL$endpoint$query" | jq '.'
    echo
}

# Function to explore classroom data
explore_classrooms() {
    echo -e "${GREEN}Exploring Classrooms Data${NC}"
    call_api "/aula" "All Classrooms"
}

# Function to explore turn details
explore_turn() {
    local turn_id=$1
    echo -e "${GREEN}Exploring Turn ID: $turn_id${NC}"
    
    call_api "/turno/$turn_id" "Turn Details"
    call_api "/horario/turno/$turn_id" "Turn Schedule"
}

# Function to explore turns with filters
explore_turns_with_filters() {
    local page=${1:-1}
    local limit=${2:-10}
    local period=${3:-"20252"}
    local faculty=${4:-""}
    local specialty=${5:-""}
    local cycle=${6:-""}
    
    echo -e "${GREEN}Exploring Turns with Filters${NC}"
    
    # Build filters array
    local filters=(
        "page=$page"
        "limit=$limit"
    )
    
    [[ -n "$period" ]] && filters+=("n_codper=$period")
    [[ -n "$faculty" ]] && filters+=("c_codfac=$faculty")
    [[ -n "$specialty" ]] && filters+=("c_codesp=$specialty")
    [[ -n "$cycle" ]] && filters+=("n_ciclo=$cycle")
    
    call_api_with_filters "/turno" "Turns List" "${filters[@]}"
}

# Function to explore filter options
explore_filter_options() {
    echo -e "${GREEN}Exploring Filter Options${NC}"
    
    call_api "/periodo" "Available Periods"
    call_api "/sigu/especialidades" "Faculties"
    
    # Example: Get specialties for a specific faculty and cycle
    call_api_with_filters "/sigu/carreras-ciclo" "Specialties (SALUD, Cycle 5)" "c_codfac=SALUD" "n_ciclo=5"
}

# Main menu
while true; do
    echo -e "${GREEN}=== API Explorer ===${NC}"
    echo "1. Explore Classrooms"
    echo "2. Explore Turn Details (requires turn ID)"
    echo "3. Explore Turns with Filters"
    echo "4. Explore Filter Options"
    echo "5. Exit"
    
    read -p "Choose an option (1-5): " choice
    
    case $choice in
        1)
            explore_classrooms
            ;;
        2)
            read -p "Enter Turn ID: " turn_id
            explore_turn "$turn_id"
            ;;
        3)
            read -p "Page (default 1): " page
            read -p "Limit (default 10): " limit
            read -p "Period (default 20252): " period
            read -p "Faculty code (optional): " faculty
            read -p "Specialty code (optional): " specialty
            read -p "Cycle (optional): " cycle
            
            explore_turns_with_filters \
                "${page:-1}" \
                "${limit:-10}" \
                "${period:-20252}" \
                "$faculty" \
                "$specialty" \
                "$cycle"
            ;;
        4)
            explore_filter_options
            ;;
        5)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
    
    echo
    read -p "Press Enter to continue..."
    clear
done
