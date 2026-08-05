import uuid
import time
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor 
import os
from flask_mysqldb import MySQL


app = Flask(__name__)
app.config['SECRET_KEY'] = 'ndala_business_secret_key_2026'

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', '127.0.0.1')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'ndala_business_db')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)


class ProduitStandard:
    def __init__(self, nom, prix_unitaire, quantite, id_db):
        self.id_db = id_db
        self.nom = nom
        self.prix_unitaire = float(prix_unitaire)
        self.quantite = int(quantite)
        self.type = "Standard"
        
    def calculer_sous_total(self):
        return self.prix_unitaire * self.quantite


class ProduitHorsListe:
    def __init__(self, nom, quantite):
        self.nom = nom
        self.quantite = int(quantite)
        self.prix_unitaire = 0.0
        self.type = "HorsListe"

    def calculer_sous_total(self):
        return 0.0


class ProduitFactory:
    @staticmethod
    def creer_produit(type_selection, nom_saisi, quantite, catalogue_db=None):
        if catalogue_db is None:
            catalogue_db = {}
            
        key = str(type_selection).lower() if type_selection else ""
        
        if key in catalogue_db:
            infos = catalogue_db[key]
            nom_orig = str(infos.get('nom_original', key))
            prix_unit = infos.get('prix_unitaire', 0.0)
            id_prod = infos.get('id', None)
            return ProduitStandard(nom_orig, prix_unit, quantite, id_prod)
            
        elif key == "autre":
            nom_clean = str(nom_saisi).strip() if nom_saisi else "Produit sur mesure"
            return ProduitHorsListe(nom_clean, quantite)
            
        raise ValueError("Impossible de fabriquer le produit : sélection invalide.")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/inscription', methods=['POST'])
def inscription():
    nom = request.form.get('nom')
    telephone = request.form.get('telephone')
    mot_de_passe = request.form.get('mot_de_passe')
    
    if not nom or not telephone or not mot_de_passe:
        flash("Veuillez remplir tous les champs.")
        return redirect(url_for('index'))
        
    try:
        with mysql.connection.cursor() as cur:  # type: ignore
            cur.execute(
                "INSERT INTO utilisateurs (nom, telephone, mot_de_passe, role) VALUES (%s, %s, %s, 'client')", 
                (nom, telephone, mot_de_passe)
            )
        mysql.connection.commit()  # type: ignore
        
        flash("Inscription réussie ! Connectez-vous.")
        return redirect(url_for('bienvenue'))
        
    except Exception:
        flash("Ce numéro de téléphone est déjà utilisé.")
        return redirect(url_for('index'))


@app.route('/bienvenue')
def bienvenue():
    return render_template('bienvenue.html')


@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        telephone = request.form.get('telephone')
        mot_de_passe = request.form.get('mot_de_passe')
        
        with mysql.connection.cursor() as cur:  # type: ignore
            cur.execute(
                "SELECT * FROM utilisateurs WHERE telephone = %s", 
                (telephone,)
            )
            utilisateur = cur.fetchone()
        
        if utilisateur and utilisateur['mot_de_passe'] == mot_de_passe:
            if utilisateur['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('mon_espace'))
        else:
            flash("Numéro ou mot de passe incorrect.")
            return redirect(url_for('connexion'))
            
    return render_template('connexion.html')


@app.route('/mon-espace')
def mon_espace():
    return render_template('mon_espace.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    try:
        conn = mysql.connection  # type: ignore
        if conn is None:
            return "Erreur de connexion MySQL", 500

        cur = conn.cursor()

        # 1. Récupérer tous les produits
        cur.execute("SELECT id, nom_produit, prix_unitaire FROM produits ORDER BY nom_produit ASC")
        produits = cur.fetchall()

        # 2. Récupérer toutes les commandes (Jointure corrigée avec la table 'transactions')
        query_commandes = """
            SELECT 
                c.id AS commande_id,
                COALESCE(u.nom, 'Client WhatsApp') AS client_nom,
                COALESCE(u.telephone, 'N/A') AS client_telephone,
                COALESCE(c.total_provisoire, 0) AS total_provisoire,
                COALESCE(c.statut, 'en_attente') AS statut_commande,
                c.date_commande,
                COALESCE(t.mode_paiement, 'WhatsApp') AS mode_paiement,
                COALESCE(t.reference_paiement, '-') AS reference_paiement
            FROM commandes c
            LEFT JOIN utilisateurs u ON c.utilisateur_id = u.id
            LEFT JOIN transactions t ON c.id = t.commande_id
            ORDER BY c.date_commande DESC
        """
        cur.execute(query_commandes)
        commandes = cur.fetchall()

        cur.close()
        return render_template('admin_dashboard.html', produits=produits, commandes=commandes)

    except Exception as e:
        print(f"Erreur Admin Dashboard : {e}")
        return render_template('admin_dashboard.html', produits=[], commandes=[])


@app.route('/catalogue')
def catalogue():
    try:
        conn = mysql.connection
        if conn is None:
            raise Exception("La connexion à MySQL a échoué (mysql.connection est None)")

        cur = conn.cursor()
        cur.execute("SELECT id, nom_produit, prix_unitaire, categorie, image_url FROM produits WHERE disponible = TRUE ORDER BY nom_produit ASC")
        tous_les_produits = cur.fetchall()
        cur.close()

        legumes = []
        epices = []

        for p in tous_les_produits:
            if isinstance(p, dict):
                cat = str(p.get('categorie', '')).strip().lower()
                prod_data = p
            else:
                cat = str(p[3]).strip().lower() if len(p) > 3 else ''
                prod_data = {
                    'id': p[0],
                    'nom_produit': p[1],
                    'prix_unitaire': p[2],
                    'categorie': p[3],
                    'image_url': p[4]
                }

            if 'epice' in cat or 'épice' in cat:
                epices.append(prod_data)
            else:
                legumes.append(prod_data)

    except Exception as e:
        print(f"ERREUR MYSQL ROUTE CATALOGUE : {e}")
        legumes = []
        epices = []

    return render_template('catalogue.html', legumes=legumes, epices=epices)


@app.route('/admin/modifier-prix', methods=['POST'])
def modifier_prix():
    produit_id = request.form.get('produit_id')
    nouveau_prix = request.form.get('nouveau_prix')

    if produit_id and nouveau_prix:
        try:
            conn = mysql.connection  # type: ignore
            if conn is None:
                return "Erreur de connexion MySQL", 500

            cur = conn.cursor()
            query = "UPDATE produits SET prix_unitaire = %s WHERE id = %s"
            cur.execute(query, (nouveau_prix, produit_id))
            
            conn.commit()
            cur.close()
            
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            print(f"ERREUR MODIFICATION PRIX : {e}")
            return f"Erreur lors de la modification : {e}", 500

    return "Données invalides", 400


@app.route('/passer_commande', methods=['POST'])
def passer_commande():
    id_utilisateur = 1 
    
    # Frais de livraison de base
    frais_livraison_base = 5000.0
    
    # 1. Récupération des données du formulaire
    sans_depot = request.form.get('sans_depot')
    montant_verse = request.form.get('montant_verse', '').strip()
    reference_paiement = request.form.get('reference_paiement', '').strip()
    mode_paiement = request.form.get('mode_paiement', '').strip()
    
    is_sans_depot = True if (sans_depot is not None and sans_depot != '') else False
    
    # Validation du formulaire si paiement avec dépôt
    if not is_sans_depot:
        if not montant_verse or not reference_paiement or not mode_paiement:
            flash("Veuillez renseigner les informations de paiement ou cocher l'option sans dépôt.")
            return redirect(url_for('catalogue'))
        
        # Vérification préventive d'unicité de la référence saisie
        try:
            with mysql.connection.cursor() as cur:  # type: ignore
                cur.execute("SELECT id FROM transactions WHERE reference_paiement = %s", (reference_paiement,))
                if cur.fetchone():
                    flash("Cette référence de paiement a déjà été utilisée pour une autre commande.")
                    return redirect(url_for('catalogue'))
        except Exception as e:
            print(f"Erreur vérification référence : {e}")

    # Récupération du catalogue
    try:
        with mysql.connection.cursor() as cur:  # type: ignore
            cur.execute("SELECT id, nom_produit, prix_unitaire FROM produits WHERE disponible = TRUE")
            resultats = cur.fetchall()
        
        catalogue_db = {
            str(row['nom_produit']).lower(): {
                'id': row['id'], 
                'prix_unitaire': float(row['prix_unitaire']),
                'nom_original': row['nom_produit']
            } 
            for row in resultats
        }
        
    except Exception as e:
        print(f"Erreur catalogue DB : {e}")
        flash("Erreur lors de la récupération du catalogue.")
        return redirect(url_for('catalogue'))
    
    choix_produits = request.form.getlist('produit[]')
    quantites = request.form.getlist('quantite[]')
    noms_autres = request.form.getlist('nom_autre[]')
    
    produits_commandes = []
    try:
        for i in range(len(choix_produits)):
            if not choix_produits[i]: 
                continue
                
            produit = ProduitFactory.creer_produit(
                type_selection=choix_produits[i],
                nom_saisi=noms_autres[i] if i < len(noms_autres) else "",
                quantite=quantites[i] if i < len(quantites) else 1,
                catalogue_db=catalogue_db
            )
            produits_commandes.append(produit)
            
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('catalogue'))

    if not produits_commandes:
        flash("Votre panier est vide.")
        return redirect(url_for('catalogue'))

    sous_total_produits = sum(p.calculer_sous_total() for p in produits_commandes)
    total_facture = sous_total_produits + frais_livraison_base
    
    # Enregistrement en BD avec gestion de transaction
    try:
        with mysql.connection.cursor() as cur:  # type: ignore
            cur.execute(
                "INSERT INTO commandes (utilisateur_id, total_provisoire, statut) VALUES (%s, %s, 'en_attente')",
                (id_utilisateur, total_facture)
            )
            id_commande = cur.lastrowid
            
            for p in produits_commandes:
                if p.type == "Standard":
                    cur.execute(
                        "INSERT INTO lignes_commande (commande_id, produit_id, nom_autre, quantite, prix_unitaire) VALUES (%s, %s, NULL, %s, %s)",
                        (id_commande, p.id_db, p.quantite, p.prix_unitaire)
                    )
                else:
                    cur.execute(
                        "INSERT INTO lignes_commande (commande_id, produit_id, nom_autre, quantite, prix_unitaire) VALUES (%s, NULL, %s, %s, 0.00)",
                        (id_commande, p.nom, p.quantite)
                    )
            
            # Insertion de la transaction de paiement
            if is_sans_depot:
                ref_unique = f"SD-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
                cur.execute(
                    "INSERT INTO transactions (commande_id, montant_verse, reference_paiement, mode_paiement, statut_transaction) VALUES (%s, 0.00, %s, %s, 'non_paye')",
                    (id_commande, ref_unique, 'WhatsApp')
                )
            else:
                ref_finale = reference_paiement if reference_paiement else f"REF-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
                montant_final = float(montant_verse) if montant_verse else 0.0
                
                cur.execute(
                    "INSERT INTO transactions (commande_id, montant_verse, reference_paiement, mode_paiement, statut_transaction) VALUES (%s, %s, %s, %s, 'a_verifier')",
                    (id_commande, montant_final, ref_finale, mode_paiement)
                )
            
        mysql.connection.commit()  # type: ignore
            
    except Exception as e:
        mysql.connection.rollback()  # type: ignore
        print(f"Erreur SQL exacte : {e}")
        flash(f"Erreur lors de l'enregistrement de la commande : {e}")
        return redirect(url_for('catalogue'))
        
    # Préparation WhatsApp
    details_texte = f"Nouvelle Commande Ndala Business (N°{id_commande})\n\n"
    for p in produits_commandes:
        if p.type == "Standard":
            details_texte += f"- {p.nom} x{p.quantite} ({p.calculer_sous_total()} FC)\n"
        else:
            details_texte += f"- {p.nom} (Hors-Liste) x{p.quantite} [Prix a fixer]\n"
            
    details_texte += f"\nSous-total produits : {sous_total_produits} FC\n"
    details_texte += f"Frais de livraison (estimatifs) : {int(frais_livraison_base)} FC*\n"
    details_texte += f"Total estimé : {total_facture} FC\n"
    details_texte += "*(Le prix de livraison peut varier selon votre commune/distance exacte)\n\n"
    
    if is_sans_depot:
        details_texte += "STATUT PAIEMENT : AUCUN DEPOT EFFECTUE\n"
        details_texte += "Le client souhaite discuter du paiement directement sur WhatsApp.\n\n"
    else:
        details_texte += f"Paiement : {montant_verse} FC via {mode_paiement}\n"
        details_texte += f"Ref SMS : {reference_paiement}\n\n"
        
    details_texte += "Veuillez m'indiquer votre commune et votre adresse exacte pour ajuster la livraison."
    
    texte_url = urllib.parse.quote(details_texte)
    lien_whatsapp = f"https://wa.me/243818378478?text={texte_url}"
    
    return redirect(lien_whatsapp)


if __name__ == '__main__':
    # host='0.0.0.0' permet à Docker d'exposer l'application sur le réseau
    app.run(host='0.0.0.0', port=5000, debug=True)